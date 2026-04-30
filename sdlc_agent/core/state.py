"""Shared state dict + checkpointing so interrupted runs can resume."""
import hashlib
import json
import time
from pathlib import Path


CHECKPOINT_DIR = Path(__file__).resolve().parent / 'checkpoints'
CHECKPOINT_DIR.mkdir(exist_ok=True)


def initial_state(idea: str) -> dict:
    return {
        'idea':        idea,
        'analysis':    None,
        'plan':        None,
        'design':      None,
        'code':        None,
        'project_dir': None,
        'tests':       None,
        'status':      'started',
        'errors':      [],
        'task_tracker': {},
    }


def validate_stage_input(state: dict, required_key: str) -> bool:
    if state.get(required_key) is None:
        state['errors'].append(f'Missing required input: {required_key}')
        return False
    return True


# ---------------- Checkpointing ----------------

def _idea_key(idea: str) -> str:
    return hashlib.md5(idea.encode()).hexdigest()[:12]


def checkpoint_path(idea: str) -> Path:
    return CHECKPOINT_DIR / f'run_{_idea_key(idea)}.json'


def save_checkpoint(state: dict) -> Path:
    """Persist the current state to disk. Called after every stage completes."""
    p = checkpoint_path(state['idea'])
    payload = dict(state)
    payload['_saved_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
    p.write_text(json.dumps(payload, indent=2, default=str))
    return p


def load_checkpoint(idea: str):
    """Return the saved state for this idea, or None if no checkpoint exists."""
    p = checkpoint_path(idea)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def clear_checkpoint(idea: str) -> bool:
    p = checkpoint_path(idea)
    if p.exists():
        p.unlink()
        return True
    return False


def list_checkpoints() -> list:
    """Return summary of every saved checkpoint, newest first."""
    out = []
    for p in CHECKPOINT_DIR.glob('run_*.json'):
        try:
            data = json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        stages_done = [
            k for k in ('analysis', 'plan', 'design', 'code', 'tests')
            if data.get(k) is not None
        ]
        out.append({
            'idea':        (data.get('idea') or '')[:160],
            'status':      data.get('status', 'unknown'),
            'stages_done': stages_done,
            'next_stage':  _next_stage(stages_done),
            'saved_at':    data.get('_saved_at', 'unknown'),
            'errors':      data.get('errors', []),
            'checkpoint_file': p.name,
        })
    out.sort(key=lambda r: r['saved_at'], reverse=True)
    return out


def _next_stage(done: list) -> str:
    order = ['analysis', 'plan', 'design', 'code', 'tests']
    for stage in order:
        if stage not in done:
            return stage
    return 'complete'
