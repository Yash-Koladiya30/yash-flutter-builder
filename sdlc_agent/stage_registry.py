"""Registry of every stage the meta-planner can schedule.

Each entry describes what the stage does, what state keys it reads/writes,
and when to skip or re-run it. The planner sees this catalog and chooses
which stages to execute, in what order.
"""
from stages import analysis, planning, design, coding, testing


STAGE_REGISTRY = {
    'analysis': {
        'module': analysis,
        'agent_name': 'Deepika',
        'description': 'Analyses the app idea. Queries past runs, engineering patterns, and competitor reviews. Produces a structured requirements document.',
        'reads':  ['idea'],
        'writes': 'analysis',
        'when_to_skip': 'When the same/very similar idea already has a cached analysis in agent memory.',
        'cost': 'medium',
    },
    'planning': {
        'module': planning,
        'agent_name': 'Aditi',
        'description': 'Decomposes the analysis into a numbered list of implementation tasks (max 8 steps).',
        'reads':  ['idea', 'analysis'],
        'writes': 'plan',
        'when_to_skip': 'When the design stage can work directly from analysis (very small apps).',
        'cost': 'low',
    },
    'design': {
        'module': design,
        'agent_name': 'Alia',
        'description': 'Produces a structured JSON spec: screens, data models, BLoCs, dependencies, acceptance criteria.',
        'reads':  ['idea', 'analysis', 'plan'],
        'writes': 'design',
        'when_to_skip': 'Never skip — coding requires a design.',
        'cost': 'medium',
    },
    'coding': {
        'module': coding,
        'agent_name': 'Priyanka',
        'description': 'Scaffolds the Flutter project, generates Dart source for models/BLoCs/screens, runs flutter analyze, fixes issues.',
        'reads':  ['design'],
        'writes': 'code',
        'when_to_skip': 'Only if user wants spec-only output.',
        'cost': 'high',
    },
    'testing': {
        'module': testing,
        'agent_name': 'Katrina',
        'description': 'Generates widget tests and BLoC unit tests, runs flutter test, reports pass/fail.',
        'reads':  ['design', 'code'],
        'writes': 'tests',
        'when_to_skip': 'When user asks for a prototype without verification.',
        'cost': 'medium',
    },
}


def describe_stages() -> str:
    """Human/LLM readable catalog of all stages."""
    lines = []
    for name, info in STAGE_REGISTRY.items():
        lines.append(
            f'- {name}: {info["description"]} '
            f'(reads: {", ".join(info["reads"])}; writes: {info["writes"]}; '
            f'cost: {info["cost"]})'
        )
    return '\n'.join(lines)


def get_stage(name: str) -> dict:
    if name not in STAGE_REGISTRY:
        raise KeyError(f'Unknown stage: {name}. Available: {list(STAGE_REGISTRY)}')
    return STAGE_REGISTRY[name]


def check_prereqs(stage_name: str, state: dict) -> list:
    """Return a list of missing required keys for this stage, [] if all satisfied."""
    info = get_stage(stage_name)
    missing = []
    for key in info['reads']:
        if state.get(key) is None:
            missing.append(key)
    return missing
