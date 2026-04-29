"""Orchestrator — planner + executor loop with checkpointing.

If a checkpoint exists for the given idea, we resume from the first unfinished stage.
After every stage completes, the full state dict is written to disk so an interrupted
run can pick up without losing earlier work.
"""
from state import initial_state, save_checkpoint, load_checkpoint
from stage_registry import STAGE_REGISTRY
from meta_planner import plan as meta_plan
from meta_executor import execute_stage
from tools.memory import store_run
from tools.jira import create_jira_issue, create_jira_subtask, jira_enabled
import time


# Granular subtasks every agent will create under their main task. The user
# sees these on the board as a checklist of what each agent will do.
STAGE_SUBTASKS = {
    'analysis': [
        'Review app idea and constraints',
        'Query past runs and engineering patterns',
        'Gather competitor / market signals',
        'Produce structured analysis JSON (problem, users, MVP, risks)',
    ],
    'planning': [
        'Translate analysis into implementation phases',
        'Order steps by dependency and delivery risk',
        'Output bounded, executable numbered plan',
    ],
    'design': [
        'Define screens and navigation graph',
        'Specify data models with typed fields',
        'Define BLoC events and states per feature',
        'Pick pub.dev dependencies and write acceptance criteria',
    ],
    'coding': [
        'Scaffold Flutter project (flutter create)',
        'Generate Dart data model classes',
        'Generate flutter_bloc files (events, states, bloc)',
        'Generate Flutter screen widgets',
        'Run flutter analyze and fix issues',
    ],
    'testing': [
        'Generate widget tests for each screen',
        'Generate BLoC unit tests',
        'Run flutter test suite',
        'Capture pass/fail with failing case details',
    ],
}

# Friendly main-task title per stage
STAGE_TITLES = {
    'analysis': 'Requirements Analysis & Specification',
    'planning': 'Strategic Implementation Roadmap',
    'design':   'System Architecture & UX Design',
    'coding':   'Core System Development & Engineering',
    'testing':  'Quality Assurance & Validation Suite',
}


def _stage_key_for_output(output_key: str) -> str:
    """Reverse-lookup the registry stage whose `writes` matches output_key."""
    for name, info in STAGE_REGISTRY.items():
        if info['writes'] == output_key:
            return name
    return output_key


def _needs_rework(state: dict) -> bool:
    """Return True if we should re-run coding+testing because tests failed
    or the analyzer still reports problems after the first pass."""
    tests = state.get('tests')
    if tests is None:
        return False
    if not tests.get('passed', False):
        return True
    # tests passed but code stage's final analyze wasn't clean → also rework
    code = state.get('code') or {}
    if code and not code.get('final_clean', True):
        return True
    return False


def _rework_reason(state: dict) -> str:
    tests = state.get('tests') or {}
    code  = state.get('code') or {}
    build = tests.get('build') or {}

    # Build / compile errors are highest priority (PhaseScript, undefined names, etc.)
    if tests and not tests.get('build_ok', True):
        errs = build.get('error_lines') or []
        if errs:
            return f"build failed: {errs[0][:140]}"
        return 'flutter build failed (compile error)'
    # Then unit/widget test assertion failures
    if tests and not tests.get('tests_ok', True):
        result = tests.get('run_result', {}) or {}
        failures = result.get('failure_lines') or []
        if failures:
            return f"flutter test failed: {failures[0][:120]}"
        return 'flutter test reported failures'
    # Legacy 'passed' field check (back-compat)
    if not tests.get('passed', True):
        return 'tests/build not passed'
    if not code.get('final_clean', True):
        passes = code.get('analyze_passes') or []
        if passes:
            issues = passes[-1].get('issues') or []
            if issues:
                return f"analyzer still dirty: {issues[0][:120]}"
        return 'flutter analyze still has issues'
    return 'unknown rework trigger'


def _project_label(state: dict, idea: str) -> str:
    """Short, board-friendly project identifier.

    Prefers design.app_name once design stage has run; otherwise derives a slug
    from the first few words of the idea.
    """
    app = (state.get('design') or {}).get('app_name')
    if app:
        return app
    import re
    s = re.sub(r'[^a-z0-9 ]', '', (idea or '').lower())
    words = [w for w in s.split() if w and w not in ('a', 'an', 'the', 'app', 'an', 'create', 'build')]
    slug = '_'.join(words[:3]) or 'app'
    return slug


def _build_rework_context(state: dict, prior_code) -> dict:
    """Package previous failure info so the coding stage knows what to fix."""
    tests = state.get('tests') or {}
    result = tests.get('run_result', {}) or {}
    build  = tests.get('build') or {}
    prior  = prior_code or {}
    analyze_passes = prior.get('analyze_passes', []) if isinstance(prior, dict) else []
    last_analyze = analyze_passes[-1] if analyze_passes else {}
    return {
        'prior_build_ok':       tests.get('build_ok', True),
        'prior_build_errors':   build.get('error_lines', []),
        'prior_build_tail':     build.get('tail', ''),
        'prior_test_output':    result.get('raw_output_tail', ''),
        'prior_test_failures':  result.get('failure_lines', []),
        'prior_analyze_issues': last_analyze.get('issues', []),
        'note': ('REWORK iteration. Build/compile errors are highest priority. '
                 'Fix Dart files (and pubspec.yaml if a package is missing), '
                 'preserve everything else.'),
    }


def _task_description_for_stage(stage_name: str, info: dict, idea: str) -> str:
    """Create a clear and detailed task description for board visibility."""
    stage_outputs = {
        'analysis': 'Structured analysis JSON with problem, users, MVP, risks, and constraints.',
        'planning': 'Prioritized and executable implementation plan with bounded steps.',
        'design': 'Schema-aligned design JSON with screens, models, dependencies, and acceptance criteria.',
        'coding': 'Runnable Flutter code artifacts with analyze results and tracked file writes.',
        'testing': 'Test execution report with pass/fail summary and failing case details.',
    }
    stage_checklist = {
        'analysis': [
            'Review app idea and constraints',
            'Gather pattern/memory/market signals',
            'Produce structured analysis output',
        ],
        'planning': [
            'Translate analysis into implementation phases',
            'Order steps by dependency and delivery risk',
            'Output concise numbered plan',
        ],
        'design': [
            'Define app architecture and navigation',
            'Specify data models, states, and dependencies',
            'Write acceptance criteria for coding/testing',
        ],
        'coding': [
            'Scaffold project and create source files',
            'Implement features from design contract',
            'Run analyze and iterate on issues',
        ],
        'testing': [
            'Generate unit/widget tests from design and code',
            'Run test suite and capture outcomes',
            'Record failures with actionable context',
        ],
    }

    checklist = '\n'.join([f'- {item}' for item in stage_checklist.get(stage_name, [])])
    return (
        f'Agent: {info.get("agent_name", "Agent")}\n'
        f'Stage: {stage_name}\n'
        f'Role: {info["description"]}\n'
        f'Goal: {idea}\n'
        f'Expected Output: {stage_outputs.get(stage_name, info["writes"])}\n'
        f'Definition of Done:\n{checklist}\n'
    )


def run_orchestrated(idea: str, fresh: bool = False, stop_event=None,
                     max_rework: int = None) -> dict:
    if max_rework is None:
        import os as _os
        try:
            max_rework = int(_os.environ.get('MAX_REWORK', '5'))
        except ValueError:
            max_rework = 5
    """Run the meta-planner + executor loop.

    stop_event: optional threading.Event — checked between stages; if set,
                the orchestrator saves the checkpoint and exits gracefully.
    max_rework: maximum rework iterations if tests fail after the initial pass.
    """
    def _should_stop():
        return stop_event is not None and stop_event.is_set()

    print(f'\n{"=" * 70}')
    print(f'[ORCHESTRATOR] Goal: {idea[:100]}')
    print(f'{"=" * 70}')

    # 1. Resume from checkpoint if one exists for this idea
    saved = None if fresh else load_checkpoint(idea)
    if saved is not None:
        state = saved
        state.setdefault('errors', [])
        state.setdefault('jira_task_map', {})
        state.setdefault('jira_subtask_map', {})
        state.setdefault('task_tracker', {})
        done = [k for k in ('analysis', 'plan', 'design', 'code', 'tests')
                if state.get(k) is not None]
        jira_main = len(state.get('jira_task_map', {}))
        jira_subs = sum(len(v) for v in state.get('jira_subtask_map', {}).values())
        print(f'[RESUME] Checkpoint loaded.')
        print(f'[RESUME] Stages done: {done or "none"}')
        print(f'[RESUME] Jira maps:   {jira_main} main tasks, {jira_subs} subtasks (will reuse, NOT recreate)')
        print(f'[RESUME] Resuming from first unfinished stage.')
    else:
        state = initial_state(idea)
        if fresh:
            print('[FRESH] Skipping any existing checkpoint.')

    # 2. Planner decides the full stage sequence (unchanged — planner is cheap)
    print('\n[PLANNER] Deciding stage sequence...')
    planned = meta_plan(state)
    print(f'[PLANNER] Plan ({planned["source"]}): {planned["plan"]}')
    print(f'[PLANNER] Rationale: {planned.get("rationale", "")}')
    if planned.get('dropped'):
        print(f'[PLANNER] Dropped invalid stages: {planned["dropped"]}')

    state['meta_plan'] = planned
    state.setdefault('execution_trace', [])
    state.setdefault('jira_task_map', {})       # stage_name -> main jira_key
    state.setdefault('jira_subtask_map', {})    # stage_name -> [subtask_keys]
    state.setdefault('task_tracker', {})        # stage_name -> task metadata/status

    # 2b. Pre-create EVERY agent's main task + subtasks (only when Jira enabled).
    #     On resume, existing keys are reused — no duplicates on the board.
    project_label = _project_label(state, idea)
    _jira_on = jira_enabled()
    if not _jira_on:
        print(f'\n[JIRA] DISABLED — skipping task creation. Project label: {project_label}')
        state['jira_task_map'] = {}
        state['jira_subtask_map'] = {}
    else:
        print(f'\n[JIRA] Project label for this run: {project_label}')
        pre_existing = sum(1 for s in planned['plan'] if s in state.get('jira_task_map', {}))
        if pre_existing:
            print(f'[JIRA] {pre_existing}/{len(planned["plan"])} stages already have tasks — reusing.')
        print('[JIRA] Creating any missing tasks (main + subtasks per agent)...')

    for stage_name in (planned['plan'] if _jira_on else []):
        info = STAGE_REGISTRY.get(stage_name)
        if info is None:
            continue

        agent_name = info.get('agent_name', 'Agent')
        friendly_title = STAGE_TITLES.get(stage_name, stage_name.capitalize())

        # ---------- Main task ----------
        if stage_name in state['jira_task_map']:
            print(f"  [JIRA] {agent_name:9} → reusing {state['jira_task_map'][stage_name]} (already created)")
        else:
            summary = f"{agent_name} / {friendly_title} · {project_label}"
            desc = _task_description_for_stage(stage_name, info, idea)
            res = create_jira_issue(summary, desc)
            if res['status'] == 'ok':
                state['jira_task_map'][stage_name] = res['key']
                state['task_tracker'][stage_name] = {
                    'summary': summary,
                    'description': desc,
                    'jira_key': res['key'],
                    'status': 'todo',
                    'updated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'subtask_keys': [],
                }
                print(f"  [JIRA] {agent_name:9} → {res['key']:10} (To Do) — {summary}")
            else:
                state['task_tracker'][stage_name] = {
                    'summary': summary, 'description': desc, 'jira_key': None,
                    'status': 'todo',
                    'updated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'jira_error': res.get('message'),
                    'subtask_keys': [],
                }
                print(f"  [JIRA] {agent_name:9} → main task FAILED: {res.get('message')}")
                continue

        parent_key = state['jira_task_map'].get(stage_name)
        if not parent_key:
            continue

        # ---------- Subtasks ----------
        existing_subs = state['jira_subtask_map'].get(stage_name, [])
        if existing_subs:
            print(f"           ↳ reusing {len(existing_subs)} subtasks ({', '.join(existing_subs)})")
            continue

        subtask_keys = []
        for sub_summary in STAGE_SUBTASKS.get(stage_name, []):
            full_summary = f"{agent_name} / {sub_summary} · {project_label}"
            sub_desc = (
                f"Parent: {parent_key} ({friendly_title})\n"
                f"Agent: {agent_name}\n"
                f"Project: {project_label}\n"
                f"Goal: {idea[:160]}"
            )
            sub_res = create_jira_subtask(parent_key, full_summary, sub_desc)
            if sub_res['status'] == 'ok':
                subtask_keys.append(sub_res['key'])
                print(f"             ↳ {sub_res['key']:10} {full_summary}")
            else:
                print(f"             ↳ subtask FAILED: {sub_res.get('message')}")
        state['jira_subtask_map'][stage_name] = subtask_keys
        state['task_tracker'][stage_name]['subtask_keys'] = subtask_keys

    # Persist immediately so a crash here doesn't lose the Jira keys
    try:
        save_checkpoint(state)
    except Exception:
        pass

    # 3. Execute each stage — skip if already complete in the checkpoint
    print('\n[EXECUTOR] Dispatching stages...')
    for stage_name in planned['plan']:
        if _should_stop():
            print(f'[PAUSE] Pause signal received — halting before {stage_name}. '
                  f'Progress is saved; resume from the Checkpoints tab.')
            state['status'] = 'paused'
            state['paused_at_stage'] = stage_name
            break

        info = STAGE_REGISTRY.get(stage_name)
        if info is None:
            print(f'  [EXEC] {stage_name}: unknown stage — skipping')
            continue

        output_key = info['writes']
        if state.get(output_key) is not None:
            print(f'  [EXEC] {stage_name}: SKIP — already in checkpoint')
            if stage_name in state['task_tracker']:
                state['task_tracker'][stage_name]['status'] = 'done'
                state['task_tracker'][stage_name]['updated_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
            state['execution_trace'].append({
                'stage':  stage_name,
                'status': 'skipped_from_checkpoint',
            })
            continue

        record = execute_stage(stage_name, state)
        state['execution_trace'].append(record)

        # Save AFTER every stage — any later crash doesn't lose this work
        try:
            save_checkpoint(state)
        except Exception as e:
            print(f'  [WARN] Checkpoint save failed: {e}')

        # Halt conditions
        if record['status'] == 'error':
            print(f'[EXECUTOR] Halting — {stage_name} raised. Checkpoint preserved; run again to resume.')
            break
        if record['status'] == 'empty_output':
            print(f'[EXECUTOR] Halting — {stage_name} produced no output.')
            state['errors'].append(f'{stage_name} produced no output')
            break
        if state['errors']:
            print(f'[EXECUTOR] Halting — errors in state: {state["errors"]}')
            break

    # 3a. Safety net — testing must run after coding even if planner dropped it.
    # Coding leaves state['code']; if tests is still None, force a testing pass so
    # the build is actually verified before we declare done.
    if (not _should_stop()
        and state.get('code') is not None
        and state.get('tests') is None
        and 'testing' not in [r.get('stage') for r in state['execution_trace']]):
        print('\n[SAFETY-NET] Plan skipped testing but code exists — forcing testing stage.')
        info = STAGE_REGISTRY.get('testing')
        if info is not None:
            record = execute_stage('testing', state)
            state['execution_trace'].append(record)
            try:
                save_checkpoint(state)
            except Exception:
                pass

    # 3b. Build verification + rework loop
    # If tests failed, run up to max_rework iterations of coding → testing to fix.
    rework_iter = 0
    while (not _should_stop()
           and rework_iter < max_rework
           and state.get('project_dir')
           and _needs_rework(state)):
        rework_iter += 1
        state.setdefault('rework_history', []).append({
            'iteration': rework_iter,
            'reason':    _rework_reason(state),
            'started':   time.strftime('%Y-%m-%d %H:%M:%S'),
        })
        print(f'\n[REWORK {rework_iter}/{max_rework}] Tests failed — '
              f'reason: {_rework_reason(state)}. Re-running coding + testing.')

        # Clear downstream outputs so the stages re-execute
        prior_code = state.get('code')
        state['code'] = None
        state['tests'] = None
        # Inject the previous failure context so the coding stage knows what to fix
        state['rework_context'] = _build_rework_context(state, prior_code)

        for stage_name in ('coding', 'testing'):
            if _should_stop():
                break
            info = STAGE_REGISTRY.get(stage_name)
            if info is None:
                continue
            record = execute_stage(stage_name, state)
            record['rework_iter'] = rework_iter
            state['execution_trace'].append(record)
            try:
                save_checkpoint(state)
            except Exception:
                pass
            if record['status'] in ('error', 'empty_output'):
                break

        # Per-iteration result log
        if state.get('tests', {}).get('passed') and state.get('code', {}).get('final_clean', True):
            print(f'[REWORK {rework_iter}/{max_rework}] FIXED — tests pass, analyzer clean.')
            break
        else:
            still = _rework_reason(state)
            print(f'[REWORK {rework_iter}/{max_rework}] Still failing: {still}')

    # Hit ceiling — log final state of bugs
    if rework_iter >= max_rework and _needs_rework(state):
        print(f'[REWORK] Reached max {max_rework} iterations — leaving remaining bugs for human review.')

    # Final status decision (don't overwrite 'paused')
    if state.get('status') != 'paused':
        if state.get('tests', {}).get('passed'):
            state['status'] = 'complete'
        elif state.get('tests') is not None:
            state['status'] = 'tests_failed'

    # 4. Summary + memory persistence
    print(f'\n{"=" * 70}')
    print(f'[ORCHESTRATOR] Final status: {state["status"]}')
    print(f'[ORCHESTRATOR] Trace:')
    for rec in state['execution_trace']:
        dur = rec.get('duration_s', 0)
        print(f'  {rec["stage"]:<10} {rec["status"]:<30} ({dur}s)')
    if state['errors']:
        print(f'[ORCHESTRATOR] Errors: {state["errors"]}')
    print(f'{"=" * 70}\n')

    if state.get('design') is not None:
        mem = store_run(state)
        if mem.get('status') == 'ok':
            print(f'[MEMORY] Stored {mem["run_id"]} ({mem["memory_size"]} runs in memory)')

    return state
