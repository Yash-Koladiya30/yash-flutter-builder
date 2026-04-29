"""Flask server that serves the animated web UI and streams pipeline runs via SSE."""
import io
import json
import os
import queue
import threading
from contextlib import redirect_stdout
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_from_directory

from llm import check_ollama_running
from orchestrator import run_orchestrated
from pipeline import run_pipeline
from stage_registry import STAGE_REGISTRY
from state import list_checkpoints, clear_checkpoint, load_checkpoint
from tools.memory import list_recent_runs, retrieve_past_run
from vector_store import stats as vector_stats


WEBAPP_DIR = Path(__file__).resolve().parent / 'webapp'

app = Flask(__name__, static_folder=str(WEBAPP_DIR), static_url_path='')

# Track active runs so we can broadcast a stop signal to them
_active_runs: dict = {}
_active_runs_lock = threading.Lock()


# ---------- static routes ----------

@app.route('/')
def index():
    return send_from_directory(str(WEBAPP_DIR), 'index.html')


# ---------- JSON API ----------

@app.route('/api/health')
def api_health():
    return jsonify({
        'ollama': check_ollama_running(),
        'vector_store': vector_stats(),
    })


@app.route('/api/stages')
def api_stages():
    payload = []
    for name, info in STAGE_REGISTRY.items():
        payload.append({
            'name': name,
            'agent_name': info.get('agent_name', ''),
            'description': info['description'],
            'reads':  info['reads'],
            'writes': info['writes'],
            'cost':   info['cost'],
        })
    return jsonify(payload)


@app.route('/api/memory')
def api_memory():
    return jsonify(list_recent_runs(limit=20))


# ---------- Checkpoints (resume) ----------

@app.route('/api/checkpoints')
def api_list_checkpoints():
    return jsonify(list_checkpoints())


@app.route('/api/checkpoints/<idea_key>', methods=['GET'])
def api_get_checkpoint(idea_key: str):
    """Fetch a single checkpoint by its 12-char idea hash."""
    for c in list_checkpoints():
        if c['checkpoint_file'].startswith(f'run_{idea_key}'):
            saved = load_checkpoint(c['idea'])
            return jsonify(saved or {})
    return jsonify({'status': 'error', 'message': 'not found'}), 404


@app.route('/api/checkpoints', methods=['DELETE'])
def api_clear_checkpoint():
    """Delete the checkpoint for a given idea. Body: {"idea": "..."}"""
    body = request.get_json(silent=True) or {}
    idea = (body.get('idea') or '').strip()
    if not idea:
        return jsonify({'status': 'error', 'message': 'missing idea'}), 400
    cleared = clear_checkpoint(idea)
    return jsonify({'status': 'ok', 'cleared': cleared})


# ---------- Stop a running pipeline ----------

@app.route('/api/stop', methods=['POST'])
def api_stop():
    """Signal any active runs to stop gracefully. Optional body: {"idea": "..."}
    to target a specific run; otherwise stops every active run."""
    body = request.get_json(silent=True) or {}
    target_idea = (body.get('idea') or '').strip()
    stopped = 0
    with _active_runs_lock:
        for run_id, ctx in list(_active_runs.items()):
            if target_idea and ctx.get('idea') != target_idea:
                continue
            ctx['stop_event'].set()
            stopped += 1
    return jsonify({'status': 'ok', 'stopped': stopped})


@app.route('/api/active')
def api_active_runs():
    """List currently running pipelines."""
    with _active_runs_lock:
        return jsonify([
            {'run_id': rid, 'idea': c.get('idea'), 'started': c.get('started')}
            for rid, c in _active_runs.items()
        ])


@app.route('/api/jira/transitions/<issue_key>')
def api_jira_transitions(issue_key: str):
    """Inspect the transitions available for any Jira issue. Useful for debugging
    why a transition didn't fire — exposes the workflow's actual id+name pairs."""
    from tools.jira import list_transitions
    return jsonify(list_transitions(issue_key))


# ---------- Jira credentials (UI form) ----------

@app.route('/api/jira/config', methods=['GET'])
def api_jira_config_get():
    """Return current Jira credential state (token always masked)."""
    from tools.jira import jira_enabled as _je
    return jsonify({
        'base_url':    os.environ.get('JIRA_BASE_URL', ''),
        'email':       os.environ.get('JIRA_EMAIL', ''),
        'project_key': os.environ.get('JIRA_PROJECT_KEY', ''),
        'has_token':   bool(os.environ.get('JIRA_API_TOKEN')),
        'enabled':     _je(),
        'configured':  bool(os.environ.get('JIRA_BASE_URL')
                            and os.environ.get('JIRA_EMAIL')
                            and os.environ.get('JIRA_API_TOKEN')),
    })


@app.route('/api/jira/config', methods=['POST'])
def api_jira_config_set():
    """Save Jira credentials + enabled flag in-memory (NOT disk).

    Body: any subset of {base_url, email, api_token, project_key, enabled}.
    enabled=False → pipeline runs without any Jira calls (no tasks, no transitions).
    """
    body = request.get_json(silent=True) or {}
    base_url    = (body.get('base_url') or '').strip().rstrip('/')
    email       = (body.get('email') or '').strip()
    api_token   = (body.get('api_token') or '').strip()
    project_key = (body.get('project_key') or '').strip()
    enabled     = body.get('enabled')  # may be True/False/None

    # Empty-string semantics on creds = clear that env var
    if 'base_url' in body:    os.environ['JIRA_BASE_URL']     = base_url
    if 'email' in body:       os.environ['JIRA_EMAIL']        = email
    if 'api_token' in body and api_token:
        os.environ['JIRA_API_TOKEN'] = api_token
    elif 'api_token' in body and api_token == '':
        os.environ.pop('JIRA_API_TOKEN', None)
    if 'project_key' in body: os.environ['JIRA_PROJECT_KEY']  = project_key
    if enabled is not None:
        os.environ['JIRA_ENABLED'] = '1' if enabled else '0'

    from tools.jira import jira_enabled as _je
    return jsonify({
        'status':  'ok',
        'message': 'Saved (in-memory).',
        'base_url':    os.environ.get('JIRA_BASE_URL', ''),
        'email':       os.environ.get('JIRA_EMAIL', ''),
        'project_key': os.environ.get('JIRA_PROJECT_KEY', ''),
        'has_token':   bool(os.environ.get('JIRA_API_TOKEN')),
        'enabled':     _je(),
    })


# ---------- Full diagnostic (Settings → Test all) ----------

@app.route('/api/diagnose')
def api_diagnose():
    """Run every system check and return structured pass/fail per check."""
    import subprocess
    from tools.file_ops import workspace_root, flutter_org
    from vector_store import stats as vector_stats
    from tools.jira import test_connection as jira_test

    checks = []

    # 1. Ollama reachable
    try:
        ollama_ok = check_ollama_running()
        checks.append({
            'id': 'ollama',
            'label': 'Ollama server',
            'ok':    ollama_ok,
            'detail': 'http://localhost:11434' if ollama_ok else 'not reachable — run `ollama serve`',
        })
    except Exception as e:
        checks.append({'id': 'ollama', 'label': 'Ollama server', 'ok': False, 'detail': str(e)})

    # 2. Required models pulled
    try:
        import ollama as _ol
        names = [m.get('name', m.get('model', '')) for m in (_ol.list().get('models') or [])]
        from config import MODELS
        wanted = set(v for v in MODELS.values() if v) or set()
        missing = [w for w in wanted if w not in names and not any(w in n for n in names)]
        checks.append({
            'id': 'models',
            'label': 'Ollama models',
            'ok':    len(missing) == 0,
            'detail': f'{len(names)} installed' + (f' — missing: {", ".join(missing)}' if missing else ''),
        })
    except Exception as e:
        checks.append({'id': 'models', 'label': 'Ollama models', 'ok': False, 'detail': str(e)})

    # 3. ChromaDB collections
    try:
        s = vector_stats()
        cols = s.get('collections', {})
        patterns = cols.get('patterns', {}).get('count', 0)
        memory   = cols.get('memory', {}).get('count', 0)
        checks.append({
            'id': 'chromadb',
            'label': 'ChromaDB',
            'ok':    patterns > 0,
            'detail': f'{patterns} pattern chunks, {memory} run memories' +
                      ('' if patterns > 0 else ' — run `python3 ingest_patterns.py`'),
        })
    except Exception as e:
        checks.append({'id': 'chromadb', 'label': 'ChromaDB', 'ok': False, 'detail': str(e)})

    # 4. Flutter CLI
    try:
        r = subprocess.run(['flutter', '--version'], capture_output=True, text=True, timeout=10)
        first_line = (r.stdout or '').splitlines()[0] if r.stdout else ''
        checks.append({
            'id': 'flutter',
            'label': 'Flutter CLI',
            'ok':    r.returncode == 0,
            'detail': first_line[:80] or 'flutter command not found',
        })
    except FileNotFoundError:
        checks.append({'id': 'flutter', 'label': 'Flutter CLI', 'ok': False, 'detail': 'not in PATH'})
    except Exception as e:
        checks.append({'id': 'flutter', 'label': 'Flutter CLI', 'ok': False, 'detail': str(e)})

    # 5. Output dir writable
    try:
        root = workspace_root()
        test_path = root / '.write_test'
        test_path.write_text('ok')
        test_path.unlink(missing_ok=True)
        checks.append({
            'id': 'output_dir',
            'label': 'Output directory',
            'ok':    True,
            'detail': str(root),
        })
    except Exception as e:
        checks.append({'id': 'output_dir', 'label': 'Output directory', 'ok': False, 'detail': str(e)})

    # 6. Flutter org configured
    try:
        org = flutter_org()
        checks.append({
            'id': 'flutter_org',
            'label': 'Flutter org',
            'ok':    bool(org),
            'detail': org or 'not set',
        })
    except Exception as e:
        checks.append({'id': 'flutter_org', 'label': 'Flutter org', 'ok': False, 'detail': str(e)})

    # 7. Jira (only if configured)
    jira_configured = bool(os.environ.get('JIRA_BASE_URL')
                           and os.environ.get('JIRA_EMAIL')
                           and os.environ.get('JIRA_API_TOKEN'))
    if jira_configured:
        try:
            jr = jira_test()
            checks.append({
                'id': 'jira',
                'label': 'Jira connection',
                'ok':    jr.get('status') == 'ok',
                'detail': (f"Connected as {jr.get('user')}" if jr.get('status') == 'ok'
                           else jr.get('message', 'unknown error')),
            })
        except Exception as e:
            checks.append({'id': 'jira', 'label': 'Jira connection', 'ok': False, 'detail': str(e)})
    else:
        checks.append({
            'id': 'jira',
            'label': 'Jira connection',
            'ok':    None,  # neutral — not configured
            'detail': 'Not configured (optional)',
        })

    summary = {
        'total':  len(checks),
        'passed': sum(1 for c in checks if c['ok'] is True),
        'failed': sum(1 for c in checks if c['ok'] is False),
        'skipped': sum(1 for c in checks if c['ok'] is None),
    }
    return jsonify({'status': 'ok', 'checks': checks, 'summary': summary})


# ---------- Native folder picker (Finder / file manager) ----------

@app.route('/api/pick-folder', methods=['POST'])
def api_pick_folder():
    """Open OS-native folder picker and return chosen absolute path.
    macOS → osascript, Linux → zenity, Windows → PowerShell.
    Server must run on the user's own machine (display required)."""
    import sys, subprocess
    body = request.get_json(silent=True) or {}
    prompt = body.get('prompt', 'Select output directory')

    if sys.platform == 'darwin':
        script = f'POSIX path of (choose folder with prompt "{prompt}")'
        cmd = ['osascript', '-e', script]
    elif sys.platform.startswith('linux'):
        cmd = ['zenity', '--file-selection', '--directory', f'--title={prompt}']
    elif sys.platform == 'win32':
        ps = (
            'Add-Type -AssemblyName System.Windows.Forms; '
            f'$f = New-Object System.Windows.Forms.FolderBrowserDialog; '
            f'$f.Description = "{prompt}"; '
            'if ($f.ShowDialog() -eq "OK") {{ Write-Output $f.SelectedPath }}'
        )
        cmd = ['powershell', '-NoProfile', '-Command', ps]
    else:
        return jsonify({'status': 'error', 'message': f'Picker unsupported on {sys.platform}'}), 400

    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        path = (r.stdout or '').strip().rstrip('/').rstrip('\\')
        if r.returncode != 0 or not path:
            return jsonify({'status': 'cancelled'})
        return jsonify({'status': 'ok', 'path': path})
    except subprocess.TimeoutExpired:
        return jsonify({'status': 'cancelled', 'message': 'picker timed out'})
    except FileNotFoundError as e:
        return jsonify({'status': 'error', 'message': f'Picker tool missing: {e}'}), 500
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ---------- General agent config (output dir, Flutter org) ----------

@app.route('/api/config', methods=['GET'])
def api_config_get():
    from tools.file_ops import workspace_root, flutter_org
    return jsonify({
        'flutter_output_dir': str(workspace_root()),
        'flutter_org':        flutter_org(),
        'max_rework':         int(os.environ.get('MAX_REWORK', '5')),
    })


@app.route('/api/config', methods=['POST'])
def api_config_set():
    """Set runtime config — output dir, Flutter org, rework cap.
    In-memory only. Body: any subset of {flutter_output_dir, flutter_org, max_rework}."""
    body = request.get_json(silent=True) or {}
    out = (body.get('flutter_output_dir') or '').strip()
    org = (body.get('flutter_org') or '').strip()
    rework = body.get('max_rework')

    if out:
        from pathlib import Path as _P
        try:
            _P(out).expanduser().mkdir(parents=True, exist_ok=True)
        except Exception as e:
            return jsonify({'status': 'error',
                            'message': f'Bad output dir: {e}'}), 400
        os.environ['FLUTTER_OUTPUT_DIR'] = str(_P(out).expanduser())
    if org:
        os.environ['FLUTTER_ORG'] = org
    if rework is not None:
        try:
            os.environ['MAX_REWORK'] = str(max(0, int(rework)))
        except (TypeError, ValueError):
            pass

    from tools.file_ops import workspace_root, flutter_org
    return jsonify({
        'status': 'ok',
        'flutter_output_dir': str(workspace_root()),
        'flutter_org':        flutter_org(),
        'max_rework':         int(os.environ.get('MAX_REWORK', '5')),
    })


@app.route('/api/jira/test', methods=['POST'])
def api_jira_test():
    """Probe Jira /myself with provided creds (or current ones if body empty).
    Doesn't save the creds — pure connectivity test."""
    from tools.jira import test_connection
    body = request.get_json(silent=True) or {}
    return jsonify(test_connection(
        base_url=body.get('base_url'),
        email=body.get('email'),
        api_token=body.get('api_token'),
    ))


@app.route('/api/memory/search')
def api_memory_search():
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify({'status': 'error', 'message': 'missing ?q='})
    return jsonify(retrieve_past_run(q, top_k=5))


# ---------- SSE streaming ----------

class _StreamSink(io.TextIOBase):
    """File-like object that pushes every line written to it into a queue."""

    def __init__(self, q: queue.Queue):
        super().__init__()
        self.q = q
        self._buf = ''

    def write(self, s: str) -> int:
        self._buf += s
        while '\n' in self._buf:
            line, self._buf = self._buf.split('\n', 1)
            self.q.put(line)
        return len(s)

    def flush(self) -> None:
        if self._buf:
            self.q.put(self._buf)
            self._buf = ''


def _sse_format(event: str, data) -> str:
    # Always JSON-encode — the client does JSON.parse on every data payload,
    # so raw strings with special chars (=, quotes, etc.) must be quoted.
    return f'event: {event}\ndata: {json.dumps(data)}\n\n'


@app.route('/api/run', methods=['POST'])
def api_run():
    body = request.get_json(silent=True) or {}
    idea = (body.get('idea') or '').strip()
    mode = body.get('mode', 'orchestrated')
    fresh = bool(body.get('fresh', False))
    if not idea:
        return jsonify({'status': 'error', 'message': 'Missing idea'}), 400

    q: queue.Queue = queue.Queue()
    final = {'state': None, 'error': None}

    stop_event = threading.Event()
    import time as _time, uuid as _uuid
    run_id = _uuid.uuid4().hex[:8]
    with _active_runs_lock:
        _active_runs[run_id] = {
            'idea':       idea,
            'stop_event': stop_event,
            'started':    _time.strftime('%Y-%m-%d %H:%M:%S'),
        }

    def worker():
        sink = _StreamSink(q)
        try:
            with redirect_stdout(sink):
                if mode == 'linear':
                    state = run_pipeline(idea)
                else:
                    state = run_orchestrated(idea, fresh=fresh, stop_event=stop_event)
            final['state'] = state
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            final['error'] = str(e)
            # Push traceback into log stream so user sees what blew up
            try:
                sink.write(f'\n[WORKER ERROR] {e}\n{tb}\n')
            except Exception:
                pass
        finally:
            sink.flush()
            with _active_runs_lock:
                _active_runs.pop(run_id, None)
            q.put(None)  # sentinel

    threading.Thread(target=worker, daemon=True).start()

    def stream():
        yield _sse_format('start', {'idea': idea, 'mode': mode})
        while True:
            item = q.get()
            if item is None:
                break
            yield _sse_format('log', item)
        payload = {
            'status': final['state']['status'] if final['state'] else 'error',
            'error':  final['error'],
            'plan':   (final['state'].get('meta_plan') if final['state'] else None),
            'trace':  (final['state'].get('execution_trace') if final['state'] else None),
            'project_dir': (final['state'].get('project_dir') if final['state'] else None),
        }
        yield _sse_format('done', payload)

    return Response(stream(), mimetype='text/event-stream', headers={
        'Cache-Control': 'no-cache',
        'X-Accel-Buffering': 'no',
    })


if __name__ == '__main__':
    print("[SERVER] Yash's Agent UI starting on http://localhost:5001")
    print(f'[SERVER] Webapp dir: {WEBAPP_DIR}')
    app.run(host='0.0.0.0', port=5001, debug=False, threaded=True)
