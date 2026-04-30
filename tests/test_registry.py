"""Verify stage registry contracts."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'sdlc_agent'))

from orchestration.registry import STAGE_REGISTRY, get_stage, check_prereqs


def test_registry_has_five_agents():
    assert set(STAGE_REGISTRY.keys()) == {'analysis', 'planning', 'design', 'coding', 'testing'}


def test_each_stage_has_required_fields():
    for name, info in STAGE_REGISTRY.items():
        for key in ('module', 'agent_name', 'description', 'reads', 'writes', 'cost'):
            assert key in info, f'Stage {name} missing {key}'


def test_agent_names_match_team():
    expected = {'Deepika', 'Aditi', 'Alia', 'Priyanka', 'Katrina'}
    actual = {info['agent_name'] for info in STAGE_REGISTRY.values()}
    assert actual == expected


def test_check_prereqs_detects_missing():
    state = {'idea': 'x'}
    missing = check_prereqs('design', state)
    assert 'analysis' in missing or 'plan' in missing
