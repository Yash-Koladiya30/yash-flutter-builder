"""Entry point.

Usage:
  python3 main.py "your app idea"          # uses meta planner + executor (default)
  python3 main.py --linear "your app idea" # uses the fixed 5-stage pipeline
"""
import json
import sys
from pathlib import Path

from core.llm import check_ollama_running


DEFAULT_IDEA = (
    'Build a Flutter app that lets users scan grocery receipts and track '
    'monthly spending by category, with a dashboard showing trends.'
)


def main():
    if not check_ollama_running():
        print('[ERROR] Ollama is not reachable on http://localhost:11434')
        print('        Start it with: ollama serve')
        print('        Then pull models: ollama pull qwen2.5-coder:7b && ollama pull nomic-embed-text')
        sys.exit(1)

    argv = sys.argv[1:]
    linear = False
    if argv and argv[0] == '--linear':
        linear = True
        argv = argv[1:]

    idea = ' '.join(argv).strip() or DEFAULT_IDEA

    if linear:
        from orchestration.pipeline import run_pipeline
        state = run_pipeline(idea)
    else:
        from orchestration.orchestrator import run_orchestrated
        state = run_orchestrated(idea)

    # Persist audit trail
    out = Path(__file__).resolve().parent / 'sdlc_output'
    out.mkdir(exist_ok=True)
    for key in ('analysis', 'plan', 'design', 'code', 'tests'):
        value = state.get(key)
        if value is None:
            continue
        (out / f'{key}.json').write_text(
            json.dumps(value, indent=2, default=str),
            encoding='utf-8',
        )

    print(f'[DONE] Audit trail: {out}')
    if state.get('project_dir'):
        print(f'[DONE] Flutter project: {state["project_dir"]}')
        print(f'       Try: cd {state["project_dir"]} && flutter pub get && flutter run')


if __name__ == '__main__':
    main()
