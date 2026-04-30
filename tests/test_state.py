"""Smoke tests for state + checkpoint helpers."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'sdlc_agent'))

from core.state import (
    initial_state,
    save_checkpoint,
    load_checkpoint,
    clear_checkpoint,
    list_checkpoints,
)


def test_initial_state_has_required_keys():
    s = initial_state('test idea')
    for key in ('idea', 'analysis', 'plan', 'design', 'code', 'tests', 'status', 'errors'):
        assert key in s
    assert s['idea'] == 'test idea'
    assert s['errors'] == []
    assert s['status'] == 'started'


def test_checkpoint_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv('CHECKPOINT_DIR', str(tmp_path))
    s = initial_state('checkpoint round trip')
    s['analysis'] = {'problem': 'x'}
    save_checkpoint(s)
    loaded = load_checkpoint('checkpoint round trip')
    assert loaded is not None
    assert loaded['analysis']['problem'] == 'x'
    assert clear_checkpoint('checkpoint round trip') is True
