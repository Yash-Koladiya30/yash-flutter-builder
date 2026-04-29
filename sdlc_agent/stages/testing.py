"""Stage 5 — Testing. Generates widget tests, runs flutter test."""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from llm import chat
from state import validate_stage_input
from tools.file_ops import write_dart_file
from tools.flutter_cli import run_flutter_test, run_flutter_pub_get, run_flutter_build
from tools.knowledge import retrieve_pattern

import os
import sys


def run(state: dict) -> dict:
    if not validate_stage_input(state, 'code'):
        return state
    print('\n[STAGE 5] Testing starting...')

    project_dir = state['project_dir']
    design = state['design']
    test_files = []

    # Widget test per screen
    for screen in design.get('screens', []):
        test_code = _generate_widget_test(screen, design)
        name = _snake(screen['name']).replace('_screen', '') + '_screen_test'
        res = write_dart_file(f'{project_dir}/test/{name}.dart', test_code)
        test_files.append(res)

    # Unit test per BLoC
    for bloc in design.get('blocs', []):
        test_code = _generate_bloc_test(bloc, design)
        name = _snake(bloc['name']).replace('_bloc', '') + '_bloc_test'
        res = write_dart_file(f'{project_dir}/test/{name}.dart', test_code)
        test_files.append(res)

    print(f'  {len(test_files)} test files written')

    # 1) flutter pub get
    print('  Running flutter pub get...')
    pub = run_flutter_pub_get(project_dir)
    print(f'    pub get success: {pub.get("success", False)}')

    # 2) Determine build targets — must verify on every target the user cares about.
    #    Override via FLUTTER_BUILD_TARGETS env (comma-sep, e.g. "apk,ios" or "apk").
    targets = _resolve_build_targets()
    print(f'  Build targets: {targets}')

    builds = {}
    aggregated_errors = []
    aggregated_tail = []
    all_builds_ok = True
    for tgt in targets:
        print(f'  Running flutter build {tgt} (debug)...')
        b = run_flutter_build(project_dir, target=tgt, flavor='debug')
        ok = b.get('success', False)
        builds[tgt] = b
        if not ok:
            all_builds_ok = False
            aggregated_errors.extend([f'[{tgt}] {ln}' for ln in b.get('error_lines', [])])
            aggregated_tail.append(f'--- {tgt} build tail ---\n{b.get("tail", "")}')
        print(f'    {tgt} build success: {ok}'
              + (f' — {len(b.get("error_lines", []))} compile errors' if not ok else ''))

    # 3) flutter test
    print('  Running flutter test...')
    result = run_flutter_test(project_dir)

    tests_ok = result.get('passed', False)
    state['tests'] = {
        'test_files_written': [t for t in test_files if t.get('status') == 'ok'],
        'run_result':  result,
        'pub_get':     pub,
        'builds':      builds,                      # per-target results
        'build_targets': targets,
        'build_ok':    all_builds_ok,
        # Aggregated for rework context (back-compat key)
        'build':       {
            'error_lines': aggregated_errors[:30],
            'tail':        '\n\n'.join(aggregated_tail)[-3000:],
            'success':     all_builds_ok,
        },
        'tests_ok':    tests_ok,
        'passed':      all_builds_ok and tests_ok,
    }
    overall = all_builds_ok and tests_ok
    state['status'] = 'complete' if overall else 'tests_failed'
    targets_summary = ', '.join(f'{t}={"✓" if builds[t].get("success") else "✗"}' for t in targets)
    print(f'[STAGE 5] Done. builds=[{targets_summary}] tests={tests_ok} → overall={overall}')
    return state


def _resolve_build_targets() -> list:
    """Return list of flutter build targets to verify against.

    Env override: FLUTTER_BUILD_TARGETS="apk,ios" or "apk" or "ios,web".
    Default: apk always (universal). Add ios if macOS + xcodebuild present.
    """
    raw = os.environ.get('FLUTTER_BUILD_TARGETS', '').strip()
    if raw:
        targets = [t.strip().lower() for t in raw.split(',') if t.strip()]
        return [t for t in targets if t in ('apk', 'ios', 'web', 'macos', 'linux', 'windows')]

    targets = ['apk']  # Android always — works cross-OS, fast, no signing
    if sys.platform == 'darwin' and _has_xcode():
        targets.append('ios')
    return targets


def _has_xcode() -> bool:
    """Quick check that Xcode + iOS SDK are available."""
    try:
        import subprocess
        r = subprocess.run(['xcodebuild', '-version'], capture_output=True, timeout=5)
        return r.returncode == 0
    except Exception:
        return False


def _snake(name: str) -> str:
    import re
    s = re.sub(r'(.)([A-Z][a-z]+)', r'\1_\2', name)
    s = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', s)
    return s.lower().replace(' ', '_')


def _generate_widget_test(screen: dict, design: dict) -> str:
    ctx = _pattern_context('flutter widget test template')
    app_name = design.get('app_name', 'my_app')
    screen_name = screen['name']
    snake = _snake(screen_name).replace('_screen', '')
    prompt = f'''Generate a Flutter widget test file.

Target: {screen_name} from package:{app_name}/screens/{snake}_screen.dart
Purpose: {screen.get('purpose', '')}

{ctx}

Requirements:
- Import flutter_test/flutter_test.dart and material.dart
- Import the screen from package:{app_name}/screens/{snake}_screen.dart
- Wrap in MaterialApp for the test
- Include at least 2 tests: "renders without error" and "displays app bar"
- Use testWidgets, pumpWidget, expect, find.byType

Output ONLY Dart code. No markdown fences, no prose.'''
    return _call_code(prompt)


def _generate_bloc_test(bloc: dict, design: dict) -> str:
    app_name = design.get('app_name', 'my_app')
    bloc_name = bloc['name']
    snake = _snake(bloc_name).replace('_bloc', '')
    prompt = f'''Generate a flutter_test unit test for a BLoC.

BLoC: {bloc_name} from package:{app_name}/blocs/{snake}_bloc.dart
Events: {bloc.get('events', [])}
States: {bloc.get('states', [])}

Requirements:
- Import flutter_test/flutter_test.dart
- Import the bloc from package:{app_name}/blocs/{snake}_bloc.dart
- One test that verifies the initial state
- Use `test(...)` from flutter_test

Output ONLY Dart code. No markdown fences, no prose.'''
    return _call_code(prompt)


def _pattern_context(query: str) -> str:
    result = retrieve_pattern(query, top_k=1)
    if result.get('status') != 'ok' or not result.get('chunks'):
        return ''
    return f'Reference pattern:\n{result["chunks"][0]["text"][:300]}\n'


def _call_code(prompt: str) -> str:
    resp = chat(
        messages=[{'role': 'user', 'content': prompt}],
        max_tokens=1536, temperature=0.15, stage='testing',
    )
    text = resp['text'] or ''
    if '```' in text:
        parts = text.split('```')
        for part in parts[1:]:
            if part.startswith('dart') or part.lstrip().startswith('import'):
                code = part[4:] if part.startswith('dart') else part
                return code.strip()
    return text.strip()
