"""Sequential pipeline orchestrator."""
from core.state import initial_state
from agents import (
    deepika  as analysis,
    aditi    as planning,
    alia     as design,
    priyanka as coding,
    katrina  as testing,
)
from tools.memory import store_run


STAGES = [
    ('analysis', analysis, 'analysis'),
    ('plan',     planning, 'plan'),
    ('design',   design,   'design'),
    ('code',     coding,   'code'),
    ('tests',    testing,  'tests'),
]


def run_pipeline(idea: str) -> dict:
    state = initial_state(idea)
    print(f'\n{"=" * 70}')
    print(f'[PIPELINE] Starting: {idea[:100]}')
    print(f'{"=" * 70}')

    for label, module, output_key in STAGES:
        try:
            state = module.run(state)
        except Exception as e:
            import traceback
            traceback.print_exc()
            state['errors'].append(f'{label}: {e}')
            print(f'[PIPELINE] Stage {label} crashed: {e}')
            break

        if state['errors']:
            print(f'[PIPELINE] Halting due to errors: {state["errors"]}')
            break

        if state.get(output_key) is None:
            state['errors'].append(f'{label} stage produced no output')
            break

    print(f'\n{"=" * 70}')
    print(f'[PIPELINE] Final status: {state["status"]}')
    if state['errors']:
        print(f'[PIPELINE] Errors: {state["errors"]}')
    print(f'{"=" * 70}\n')

    # Persist the run to agent memory for future retrieval
    if state.get('design') is not None:
        mem_result = store_run(state)
        if mem_result.get('status') == 'ok':
            print(f'[MEMORY] Stored run {mem_result["run_id"]} '
                  f'({mem_result["memory_size"]} runs in memory)')
        else:
            print(f'[MEMORY] Store failed: {mem_result.get("message")}')

    return state
