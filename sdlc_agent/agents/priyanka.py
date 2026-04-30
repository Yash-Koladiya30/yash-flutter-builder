"""Stage 4 — Coding. ReAct agent with file + CLI tools.

Approach: deterministic scaffolding (flutter create + pubspec + file generation via LLM)
with an agent-driven fix-up loop for analyze errors. Tool-calling small local models
struggle with many file writes in sequence, so we drive the initial writes directly
and reserve the agent loop for the more reasoning-heavy repair step.
"""
import json
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from core.llm import chat
from core.state import validate_stage_input
from core.agent import run_agent
from tools.file_ops import (
    FILE_TOOL_SCHEMAS, FILE_TOOL_MAP,
    create_flutter_project, write_dart_file,
)
from tools.flutter_cli import (
    CLI_TOOL_SCHEMAS, CLI_TOOL_MAP, run_flutter_analyze,
)
from tools.knowledge import retrieve_pattern


FIX_SYSTEM_PROMPT = '''You are a senior Flutter engineer fixing `flutter analyze` errors in a Flutter 3.x / Dart 3 project.
Use the Material 3 API surface (FilledButton, not RaisedButton) and null safety rules.

Workflow:
1. Read the affected .dart file with read_dart_file.
2. Identify the exact analyzer issue (undefined_identifier, missing_required_argument, invalid_override, etc).
3. Rewrite the whole file with write_dart_file — keep the class name, imports, and public API identical.
4. Call run_flutter_analyze to verify.
5. Stop when analyze reports 0 issues or after 2 attempts.

Constraints:
- Only edit Dart files inside lib/ or pubspec.yaml — never touch platform/native folders.
- Preserve the BLoC pattern, go_router routes, and Hive boxes that already exist.
- Keep responses minimal — just use the tools. No commentary between tool calls.'''


def run(state: dict) -> dict:
    if not validate_stage_input(state, 'design'):
        return state

    rework_ctx = state.get('rework_context')
    if rework_ctx:
        print('\n[STAGE 4] REWORK iteration — fixing previous failures.')
        print(f'  Prior test failures: {len(rework_ctx.get("prior_test_failures", []))}')
        print(f'  Prior analyzer issues: {len(rework_ctx.get("prior_analyze_issues", []))}')
    else:
        print('\n[STAGE 4] Coding starting...')

    design = state['design']
    files_written = []

    # 1) Scaffold the Flutter project
    app_name = design.get('app_name', 'my_app')
    create_result = create_flutter_project(name=app_name)
    if create_result['status'] != 'ok':
        state['errors'].append(f'create_flutter_project failed: {create_result["message"]}')
        return state
    project_dir = create_result['project_dir']
    state['project_dir'] = project_dir
    print(f'  Project at: {project_dir}')

    # 2) Write pubspec.yaml with dependencies
    pubspec = _generate_pubspec(app_name, design.get('dependencies', []))
    res = write_dart_file(f'{project_dir}/pubspec.yaml', pubspec)
    files_written.append(res)

    # 3) Generate source files via LLM (one focused call per group)
    print('  Generating data models...')
    for model in design.get('data_models', []):
        code = _generate_model(model)
        name = _snake(model['name'])
        res = write_dart_file(f'{project_dir}/lib/models/{name}.dart', code)
        files_written.append(res)

    print('  Generating BLoCs...')
    for bloc in design.get('blocs', []):
        code = _generate_bloc(bloc)
        name = _snake(bloc['name']).replace('_bloc', '') + '_bloc'
        res = write_dart_file(f'{project_dir}/lib/blocs/{name}.dart', code)
        files_written.append(res)

    print('  Generating screens...')
    for screen in design.get('screens', []):
        code = _generate_screen(screen, design)
        name = _snake(screen['name']).replace('_screen', '') + '_screen'
        res = write_dart_file(f'{project_dir}/lib/screens/{name}.dart', code)
        files_written.append(res)

    print('  Generating main.dart...')
    main_code = _generate_main(design)
    res = write_dart_file(f'{project_dir}/lib/main.dart', main_code)
    files_written.append(res)

    # 4) Run analyze, let the agent fix issues if any
    print('  Running flutter analyze...')
    analyze = run_flutter_analyze(project_dir)
    analyze_passes = [analyze]

    # Combine analyzer issues + any rework context (previous test failures)
    dirty = analyze.get('status') == 'ok' and not analyze.get('clean')
    if dirty or rework_ctx:
        issues_block = '\n'.join(analyze.get('issues', [])[:20]) if dirty else '(analyzer clean)'
        rework_block = ''
        if rework_ctx:
            build_errors = rework_ctx.get('prior_build_errors', [])
            build_tail   = rework_ctx.get('prior_build_tail', '')
            test_fails   = rework_ctx.get('prior_test_failures', [])
            test_tail    = rework_ctx.get('prior_test_output', '')
            build_ok     = rework_ctx.get('prior_build_ok', True)

            parts = []
            if not build_ok:
                parts.append(
                    '\n\nBUILD FAILED (compile error — highest priority). '
                    'Fix Dart code or pubspec.yaml so flutter build apk succeeds.\n'
                    f'Compile errors:\n' + '\n'.join(build_errors[:15]) +
                    f'\n\nBuild output tail:\n{build_tail[-1800:]}'
                )
            if test_fails or test_tail:
                parts.append(
                    '\n\nTEST RUN FAILED. Fix root cause in lib/ or test/.\n'
                    f'Failing test lines:\n' + '\n'.join(test_fails[:10]) +
                    f'\n\nTest output tail:\n{test_tail[-1200:]}'
                )
            rework_block = ''.join(parts)
        fix_task = (
            f'The Flutter project at {project_dir} needs fixes.\n'
            f'Analyzer issues:\n{issues_block}{rework_block}\n\n'
            'Read the affected files, rewrite them to fix the issues. '
            'After edits run flutter analyze, then run flutter build apk --debug '
            'to verify it compiles. Stop when build is clean or after 4 attempts.'
        )
        tools = FILE_TOOL_SCHEMAS + CLI_TOOL_SCHEMAS
        tool_map = {**FILE_TOOL_MAP, **CLI_TOOL_MAP}
        n_build_err = len((rework_ctx or {}).get('prior_build_errors', []))
        n_test_fail = len((rework_ctx or {}).get('prior_test_failures', []))
        print(f'  {analyze.get("issue_count", 0)} analyzer issues, '
              f'{n_build_err} build errors, {n_test_fail} test failures — '
              f'asking agent to fix...')
        run_agent(fix_task, tools, tool_map, system=FIX_SYSTEM_PROMPT,
                  max_steps=10, stage='coding_fix_loop')
        analyze_passes.append(run_flutter_analyze(project_dir))

    state['code'] = {
        'project_dir': project_dir,
        'files_written': [f for f in files_written if f.get('status') == 'ok'],
        'analyze_passes': analyze_passes,
        'final_clean': analyze_passes[-1].get('clean', False),
        'was_rework':  bool(rework_ctx),
    }
    state['status'] = 'code_done'
    # Clear the rework context so it isn't reused if a later stage reloads state
    if rework_ctx:
        state.pop('rework_context', None)
    print(f'[STAGE 4] Done. {len(files_written)} files written. '
          f'Analyze clean: {state["code"]["final_clean"]}')
    return state


def _snake(name: str) -> str:
    import re
    s = re.sub(r'(.)([A-Z][a-z]+)', r'\1_\2', name)
    s = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', s)
    return s.lower().replace(' ', '_')


def _generate_pubspec(app_name: str, deps: list) -> str:
    allowed = {'flutter_bloc', 'equatable', 'go_router', 'hive', 'hive_flutter',
               'path_provider', 'intl', 'http', 'shared_preferences'}
    chosen = [d for d in deps if d in allowed]
    dep_lines = '\n'.join(f'  {d}: any' for d in chosen)
    return f'''name: {app_name}
description: Generated by SDLC Agent.
publish_to: "none"
version: 0.1.0

environment:
  sdk: ">=3.0.0 <4.0.0"

dependencies:
  flutter:
    sdk: flutter
  cupertino_icons: ^1.0.2
{dep_lines}

dev_dependencies:
  flutter_test:
    sdk: flutter
  flutter_lints: ^3.0.0

flutter:
  uses-material-design: true
'''


def _generate_model(model: dict) -> str:
    ctx = _pattern_context('dart data model with null safety and equatable')
    prompt = f'''Generate a Dart data model class.

Name: {model['name']}
Fields: {json.dumps(model.get('fields', []))}

{ctx}

Requirements:
- Null-safe types
- const constructor
- fromJson / toJson
- Extends Equatable from package:equatable/equatable.dart

Output ONLY the Dart code. No markdown fences.'''
    return _call_code(prompt)


def _generate_bloc(bloc: dict) -> str:
    ctx = _pattern_context('flutter_bloc pattern with events and states')
    prompt = f'''Generate a flutter_bloc BLoC.

Name: {bloc['name']}
Events: {bloc.get('events', [])}
States: {bloc.get('states', [])}

{ctx}

Requirements:
- Use flutter_bloc (not bloc)
- Define sealed events and states
- Use on<Event>() handlers
- Include imports for flutter_bloc and equatable

Output ONLY the Dart code. No markdown fences.'''
    return _call_code(prompt)


def _generate_screen(screen: dict, design: dict) -> str:
    bloc_names = [b['name'] for b in design.get('blocs', [])]
    ctx = _pattern_context(f'flutter screen template with {screen["name"]} widgets')
    prompt = f'''Generate a Flutter screen widget (Dart 3, Material 3, null-safe).

Name: {screen['name']}
Purpose: {screen.get('purpose', '')}
Key widgets to include: {screen.get('widgets', [])}
Available BLoCs: {bloc_names}

{ctx}

Requirements:
- Import 'package:flutter/material.dart'.
- If a BLoC is relevant, import 'package:flutter_bloc/flutter_bloc.dart' and use BlocBuilder.
- Class extends StatelessWidget (prefer) or StatefulWidget (only if controllers or tickers are needed).
- Root widget is Scaffold with an AppBar containing a Text title.
- Use const constructors wherever possible.
- Long content must be scrollable (ListView, SingleChildScrollView, or CustomScrollView).
- Use FilledButton (Material 3) not RaisedButton (removed).
- Wrap tap targets in InkWell or use ListTile/ElevatedButton for ripple.
- No hardcoded colors — use Theme.of(context).colorScheme.
- Dispose any TextEditingController/AnimationController in dispose().

Output ONLY the Dart code. No markdown fences, no prose.'''
    return _call_code(prompt)


def _generate_main(design: dict) -> str:
    screens = design.get('screens', [])
    first_screen = screens[0]['name'] if screens else 'HomeScreen'
    screen_imports = '\n'.join(
        f"import 'screens/{_snake(s['name']).replace('_screen','')}_screen.dart';"
        for s in screens
    )
    return f'''import 'package:flutter/material.dart';
{screen_imports}

void main() {{
  runApp(const MyApp());
}}

class MyApp extends StatelessWidget {{
  const MyApp({{super.key}});

  @override
  Widget build(BuildContext context) {{
    return MaterialApp(
      title: '{design.get("app_name", "Generated App")}',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.indigo),
        useMaterial3: true,
      ),
      home: const {first_screen}(),
    );
  }}
}}
'''


def _pattern_context(query: str) -> str:
    result = retrieve_pattern(query, top_k=2)
    if result.get('status') != 'ok' or not result.get('chunks'):
        return ''
    excerpts = '\n'.join(f'- {c["text"][:200]}' for c in result['chunks'])
    return f'Reference patterns from knowledge base:\n{excerpts}\n'


def _call_code(prompt: str) -> str:
    resp = chat(
        messages=[{'role': 'user', 'content': prompt}],
        max_tokens=2048, temperature=0.15, stage='coding',
    )
    text = resp['text'] or ''
    if '```' in text:
        parts = text.split('```')
        for part in parts[1:]:
            if part.startswith('dart') or part.lstrip().startswith('import'):
                code = part[4:] if part.startswith('dart') else part
                return code.strip()
    return text.strip()
