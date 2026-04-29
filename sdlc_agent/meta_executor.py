"""Meta-executor: dispatches a single stage by name, with prereq validation and tracing.

Day 3 executor pattern, lifted to the stage level. The planner tells it WHAT to run;
the executor handles HOW: check deps, invoke the stage module, capture timing and result.
"""
import time
import json

from stage_registry import get_stage, check_prereqs
from tools.jira import create_jira_issue, transition_to_status, jira_enabled


def execute_stage(stage_name: str, state: dict) -> dict:
    """Run one stage. Returns {stage, status, duration_s, missing, error?}."""
    info = get_stage(stage_name)
    record = {
        'stage':    stage_name,
        'cost':     info['cost'],
        'started':  time.strftime('%H:%M:%S'),
    }

    missing = check_prereqs(stage_name, state)
    if missing:
        state.setdefault('task_tracker', {})
        state['task_tracker'].setdefault(stage_name, {})
        state['task_tracker'][stage_name]['status'] = 'blocked'
        state['task_tracker'][stage_name]['updated_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
        state['task_tracker'][stage_name]['reason'] = f'Missing prereqs: {", ".join(missing)}'
        record.update({
            'status':  'skipped',
            'missing': missing,
            'reason':  f'Missing prereqs: {", ".join(missing)}',
        })
        print(f'  [EXEC] {stage_name}: SKIP (missing {missing})')
        return record

    t0 = time.time()
    
    # Create Jira task for the agent's work with professional requirements
    agent_name = info.get('agent_name', 'Agent')
    
    # Map stages to professional task titles
    stage_titles = {
        'analysis': f'Requirements Analysis & Specification',
        'planning': f'Strategic Implementation Roadmap',
        'design':   f'System Architecture & UX Design',
        'coding':   f'Core System Development & Engineering',
        'testing':  f'Quality Assurance & Validation Suite',
    }
    
    friendly_title = stage_titles.get(stage_name, stage_name.capitalize())
    task_summary = f"{agent_name} ({stage_name.capitalize()}) - {friendly_title} for {state.get('idea', 'App')[:40]}"
    
    # Build detailed, structured requirement description
    desc_parts = [
        f"h1. Agent Assignment: {agent_name}",
        f"h2. Phase: {friendly_title}",
        f"h3. Project Goal: {state.get('idea', 'N/A')}",
        f"\n*Role Description:* {info['description']}",
    ]
    
    # Add contextual requirements
    if stage_name == 'planning' and state.get('analysis'):
        desc_parts.append(f"\nh2. Input: Analysis Results\n{{code:json}}\n{json.dumps(state['analysis'], indent=2)[:1000]}\n{{code}}")
    elif stage_name == 'design' and state.get('plan'):
        desc_parts.append(f"\nh2. Input: Implementation Plan\n{{code:json}}\n{json.dumps(state['plan'], indent=2)[:1000]}\n{{code}}")
    elif stage_name == 'coding' and state.get('design'):
        design = state['design']
        screens = "\n".join([f"* {s.get('name', '?')}: {s.get('purpose', '')}" for s in design.get('screens', [])])
        models = ", ".join([m.get('name', '?') for m in design.get('data_models', [])])
        desc_parts.append(f"\nh2. Functional Requirements\nh3. Screens to Implement:\n{screens}\n\nh3. Data Models:\n{models}")
    elif stage_name == 'testing' and state.get('design'):
        desc_parts.append(f"\nh2. QA Requirements\nVerify system against defined architecture and acceptance criteria.")

    task_desc = "\n".join(desc_parts)
    
    # Use pre-created Jira task key (only when Jira is enabled)
    _jira_on = jira_enabled()
    jira_key = state.get('jira_task_map', {}).get(stage_name)
    if not _jira_on:
        pass  # silent — orchestrator already logged DISABLED
    elif jira_key:
        print(f"  [JIRA] Using pre-created task {jira_key} for {agent_name}")
        record['jira_key'] = jira_key
    else:
        # Fallback: create task on-the-fly if not pre-created
        print(f"  [JIRA] Creating task for {agent_name} (fallback)...")
        jira_res = create_jira_issue(task_summary, task_desc)
        if jira_res['status'] == 'ok':
            print(f"  [JIRA] Created (To Do): {jira_res['key']} ({jira_res['url']})")
            record['jira_key'] = jira_res['key']
        else:
            print(f"  [JIRA] Failed to create task: {jira_res.get('message')}")

    try:
        module = info['module']
        state.setdefault('task_tracker', {})
        state['task_tracker'].setdefault(stage_name, {})
        state['task_tracker'][stage_name]['status'] = 'in_progress'
        state['task_tracker'][stage_name]['updated_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
        state['task_tracker'][stage_name]['jira_key'] = record.get('jira_key')
        state['task_tracker'][stage_name]['description'] = task_desc

        subtask_keys = state.get('jira_subtask_map', {}).get(stage_name, [])

        # ── Transition: main task To Do → In Progress (agent starts work) ──
        if record.get('jira_key'):
            print(f"  [JIRA] {record['jira_key']} → In Progress (main)")
            transition_to_status(record['jira_key'], 'In Progress')
            # Move every subtask to In Progress so the board shows live activity
            for sk in subtask_keys:
                transition_to_status(sk, 'In Progress')
            if subtask_keys:
                print(f"  [JIRA] {len(subtask_keys)} subtasks → In Progress")

        module.run(state)

        # ── Transition: In Progress → Done (agent finished) ──
        if record.get('jira_key'):
            # Mark all child subtasks Done first, then the parent
            for sk in subtask_keys:
                transition_to_status(sk, 'Done')
            if subtask_keys:
                print(f"  [JIRA] {len(subtask_keys)} subtasks → Done")
            print(f"  [JIRA] {record['jira_key']} → Done (main)")
            transition_to_status(record['jira_key'], 'Done')

        record.update({
            'status':     'ok',
            'duration_s': round(time.time() - t0, 2),
            'wrote':      info['writes'],
            'output_empty': state.get(info['writes']) is None,
        })
        if record['output_empty']:
            record['status'] = 'empty_output'
            state['task_tracker'][stage_name]['status'] = 'blocked'
            state['task_tracker'][stage_name]['reason'] = 'Stage produced empty output'
        else:
            state['task_tracker'][stage_name]['status'] = 'done'
        state['task_tracker'][stage_name]['updated_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
        print(f'  [EXEC] {stage_name}: {record["status"]} in {record["duration_s"]}s')
    except Exception as e:
        import traceback
        record.update({
            'status':     'error',
            'duration_s': round(time.time() - t0, 2),
            'error':      str(e),
            'traceback':  traceback.format_exc(),
        })
        state['errors'].append(f'{stage_name}: {e}')
        state.setdefault('task_tracker', {})
        state['task_tracker'].setdefault(stage_name, {})
        state['task_tracker'][stage_name]['status'] = 'failed'
        state['task_tracker'][stage_name]['updated_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
        state['task_tracker'][stage_name]['reason'] = str(e)
        print(f'  [EXEC] {stage_name}: ERROR — {e}')
        # ── Keep task In Progress but log the error ──
        if record.get('jira_key'):
            print(f"  [JIRA] {record['jira_key']} stays In Progress (error occurred)")

    return record
