"""Unit tests for chat thread message limits (loads thread_limits without full analytiq_data tree)."""

import importlib.util
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_TL_PATH = _ROOT / "analytiq_data/agent/thread_limits.py"
_spec = importlib.util.spec_from_file_location("thread_limits", _TL_PATH)
assert _spec and _spec.loader
_tl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_tl)
MAX_STORED_MESSAGES = _tl.MAX_STORED_MESSAGES
trim_stored_messages = _tl.trim_stored_messages


def test_trim_stored_messages_under_limit():
    msgs = [{"role": "user", "content": str(i)} for i in range(10)]
    assert trim_stored_messages(msgs) == msgs


def test_trim_stored_messages_exactly_limit():
    msgs = [{"role": "user", "content": str(i)} for i in range(MAX_STORED_MESSAGES)]
    out = trim_stored_messages(msgs)
    assert len(out) == MAX_STORED_MESSAGES
    assert out == msgs


def test_trim_stored_messages_over_limit_keeps_last():
    msgs = [{"role": "user", "content": str(i)} for i in range(MAX_STORED_MESSAGES + 10)]
    out = trim_stored_messages(msgs)
    assert len(out) == MAX_STORED_MESSAGES
    assert out[0]["content"] == "10"
    assert out[-1]["content"] == str(MAX_STORED_MESSAGES + 9)


def test_trim_stored_messages_empty():
    assert trim_stored_messages([]) == []
