"""Meta-planner: decides which SDLC stages to run, in what order, for a given goal.

Day 3 planner pattern applied one level up. Instead of decomposing a task into tool
calls, it decomposes a goal into a sequence of SDLC stages from the registry.
"""
import json
import re

from llm import chat
from stage_registry import STAGE_REGISTRY, describe_stages
from tools.memory import retrieve_past_run


SYSTEM_PROMPT = '''You are a meta-planner for a Flutter SDLC agent.

Given a user goal and the current state, decide which SDLC stages to run and in what order.

Available stages:
{catalog}

Rules:
1. Output ONLY a JSON object: {{"plan": ["stage1", "stage2", ...], "rationale": "<one sentence>"}}.
2. Stage names MUST be from the catalog above.
3. Respect data dependencies: a stage can only run if its "reads" keys will be populated
   by a previous stage or are already in state.
4. If a similar past run is cited, you MAY skip 'analysis' and include a shortcut.
5. For a brand-new idea: plan = ["analysis","planning","design","coding","testing"].
6. For a spec-only request: plan = ["analysis","planning","design"] (no coding/testing).
7. For a "fix the tests" request: plan = ["testing"] (requires design+code already in state).
8. Never include a stage whose dependencies cannot be satisfied.
9. No prose outside the JSON.'''


def _intent_hints(state: dict) -> str:
    """Build a small context block describing state and memory hits."""
    idea = state.get('idea', '')
    hits = retrieve_past_run(idea, top_k=2)
    hint_lines = [f'User goal: {idea}']
    present = [k for k in ('analysis', 'plan', 'design', 'code', 'tests')
               if state.get(k) is not None]
    hint_lines.append(f'State already contains: {present or "nothing"}')

    if hits.get('status') == 'ok' and hits.get('runs'):
        hint_lines.append('Similar past runs from memory:')
        for r in hits['runs']:
            hint_lines.append(
                f'  - app={r.get("app_name")} '
                f'idea={(r.get("idea") or "")[:80]} '
                f'status={r.get("status")}'
            )
    else:
        hint_lines.append('No similar past runs in memory.')
    return '\n'.join(hint_lines)


def plan(state: dict) -> dict:
    """Produce an ordered list of stage names to execute."""
    system = SYSTEM_PROMPT.format(catalog=describe_stages())
    user = _intent_hints(state) + '\n\nReturn the JSON plan.'

    resp = chat(
        messages=[{'role': 'user', 'content': user}],
        system=system, max_tokens=512, temperature=0.1, stage='meta_planner',
    )
    text = resp['text'] or ''
    parsed = _extract_json(text)

    if not parsed or 'plan' not in parsed:
        # Conservative fallback: the classic full 5-stage run
        return {
            'plan': ['analysis', 'planning', 'design', 'coding', 'testing'],
            'rationale': 'Fallback: planner output could not be parsed.',
            'source': 'fallback',
        }

    valid = [s for s in parsed['plan'] if s in STAGE_REGISTRY]
    dropped = [s for s in parsed['plan'] if s not in STAGE_REGISTRY]
    return {
        'plan': valid,
        'rationale': parsed.get('rationale', ''),
        'dropped': dropped,
        'source': 'llm',
    }


def _extract_json(text: str):
    match = re.search(r'\{[\s\S]*\}', text)
    if not match:
        return None
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return None
