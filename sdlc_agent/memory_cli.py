"""Browse and manage the agent's long-term memory.

Usage:
  python3 memory_cli.py list            # list recent runs
  python3 memory_cli.py search <query>  # semantic search over past runs
  python3 memory_cli.py stats           # show ChromaDB collection sizes
  python3 memory_cli.py clear           # wipe memory (asks for confirmation)
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent))

from tools.memory import list_recent_runs, retrieve_past_run, clear_memory
from tools.vector_store import stats


def cmd_list():
    result = list_recent_runs(limit=50)
    if result['status'] != 'ok':
        print(f'Error: {result.get("message")}')
        return
    if result['total'] == 0:
        print('Memory is empty. Run `python3 main.py ...` to populate it.')
        return
    print(f'\n{result["total"]} runs in memory:\n')
    print(f'{"TIMESTAMP":<20} {"STATUS":<16} {"APP":<20} IDEA')
    print('-' * 100)
    for r in result['runs']:
        print(f'{r.get("timestamp", "?"):<20} {r.get("status", "?"):<16} '
              f'{(r.get("app_name") or "?")[:18]:<20} {(r.get("idea") or "")[:50]}')


def cmd_search(query: str):
    result = retrieve_past_run(query, top_k=5)
    if result['status'] != 'ok':
        print(f'Error: {result.get("message")}')
        return
    if not result.get('runs'):
        print('No matching runs found.')
        return
    print(f'\nTop {result["count"]} matches for: "{query}"\n')
    for i, r in enumerate(result['runs'], 1):
        print(f'[{i}] {r.get("app_name")} — {r.get("timestamp")} ({r.get("status")})')
        print(f'    Idea: {(r.get("idea") or "")[:120]}')
        print(f'    Summary: {r["summary"][:200]}')
        print()


def cmd_stats():
    s = stats()
    print(f'\nChromaDB path: {s["path"]}\n')
    print(f'{"KEY":<12} {"COLLECTION":<24} COUNT')
    print('-' * 55)
    for key, info in s['collections'].items():
        count = info.get('count', info.get('error', '?'))
        print(f'{key:<12} {info.get("name", "?"):<24} {count}')
    print()


def cmd_clear():
    resp = input('Wipe all memory? This cannot be undone. [y/N] ')
    if resp.strip().lower() != 'y':
        print('Aborted.')
        return
    result = clear_memory()
    print(result.get('message', result))


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == 'list':
        cmd_list()
    elif cmd == 'search':
        if len(sys.argv) < 3:
            print('Usage: memory_cli.py search <query>')
            sys.exit(1)
        cmd_search(' '.join(sys.argv[2:]))
    elif cmd == 'stats':
        cmd_stats()
    elif cmd == 'clear':
        cmd_clear()
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == '__main__':
    main()
