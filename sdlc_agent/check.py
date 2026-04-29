"""Quick health check — run this before main.py to confirm everything works."""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent))

from core.llm import check_ollama_running, chat, embed


def check(label: str, ok: bool, detail: str = ''):
    mark = 'OK  ' if ok else 'FAIL'
    print(f'  [{mark}] {label}' + (f' — {detail}' if detail else ''))
    return ok


def main():
    print("\n=== Yash's Agent — Health Check ===\n")
    all_ok = True

    # 1. Ollama server
    running = check_ollama_running()
    all_ok &= check('Ollama server reachable', running, 'http://localhost:11434')
    if not running:
        print('\n  Fix: run `ollama serve` in another terminal.\n')
        sys.exit(1)

    # 2. Chat model
    try:
        resp = chat(messages=[{'role': 'user', 'content': 'Say OK in one word.'}], max_tokens=8)
        ok = bool(resp.get('text'))
        all_ok &= check('Chat model responds', ok, resp['text'][:50])
    except Exception as e:
        all_ok &= check('Chat model responds', False, str(e))

    # 3. Tool calling
    try:
        tools = [{'type': 'function', 'function': {
            'name': 'echo',
            'description': 'Echo a message',
            'parameters': {'type': 'object', 'properties': {'msg': {'type': 'string'}}, 'required': ['msg']},
        }}]
        resp = chat(messages=[{'role': 'user', 'content': 'Call echo with msg="hello"'}],
                    tools=tools, max_tokens=128)
        supports_tools = resp['stop_reason'] == 'tool_use' or 'echo' in str(resp)
        all_ok &= check('Tool calling supported', supports_tools,
                        f'stop_reason={resp["stop_reason"]}')
    except Exception as e:
        all_ok &= check('Tool calling supported', False, str(e))

    # 4. Embeddings
    try:
        vec = embed('test')
        ok = isinstance(vec, list) and len(vec) > 100
        all_ok &= check('Embeddings work', ok, f'dim={len(vec) if ok else "?"}')
    except Exception as e:
        all_ok &= check('Embeddings work', False, str(e))

    # 5. Flutter CLI
    import subprocess
    try:
        r = subprocess.run(['flutter', '--version'], capture_output=True, text=True, timeout=30)
        ok = r.returncode == 0
        first_line = r.stdout.splitlines()[0] if r.stdout else ''
        all_ok &= check('Flutter CLI available', ok, first_line[:60])
    except FileNotFoundError:
        all_ok &= check('Flutter CLI available', False, 'not in PATH')

    # 6 & 7. ChromaDB collections
    try:
        from tools.vector_store import stats
        s = stats()
        print(f'  [INFO] ChromaDB path: {s["path"]}')
        patterns = s['collections'].get('patterns', {})
        memory   = s['collections'].get('memory', {})

        p_count = patterns.get('count', 0)
        all_ok &= check('Pattern KB seeded', p_count > 0, f'{p_count} chunks')
        if p_count == 0:
            print('     -> run: python3 ingest_patterns.py')

        m_count = memory.get('count', 0)
        check('Agent memory ready', True,
              f'{m_count} past runs' if m_count else 'empty (fills on first run)')
    except Exception as e:
        all_ok &= check('ChromaDB accessible', False, str(e))

    print()
    if all_ok:
        print('All checks passed. Run: python3 main.py "your app idea"')
    else:
        print('Some checks failed. Fix the issues above before running main.py.')
    sys.exit(0 if all_ok else 1)


if __name__ == '__main__':
    main()
