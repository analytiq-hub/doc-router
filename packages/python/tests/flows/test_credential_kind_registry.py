"""Tests for ``credential_kind_registry`` ``extends`` resolution and cycle detection."""

from __future__ import annotations

import pytest

from analytiq_data.flows.credential_kind_registry import _resolve_kind_with_extends


def _minimal_kind(key: str, **extra: object) -> dict[str, object]:
    base = {
        "key": key,
        "display_name": key,
        "auth_mode": "api_key",
        "secret_schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {},
            "required": [],
        },
    }
    base.update(extra)
    return base


def test_resolve_extends_linear_chain():
    store = {
        "base": _minimal_kind("base"),
        "mid": _minimal_kind("mid", extends="base"),
        "leaf": _minimal_kind("leaf", extends="mid"),
    }
    out = _resolve_kind_with_extends("leaf", store, ())
    assert out["key"] == "leaf"


def test_cycle_ab_a_raises_ordered_message():
    store = {
        "A": _minimal_kind("A", extends="B"),
        "B": _minimal_kind("B", extends="A"),
    }
    with pytest.raises(ValueError, match=r"circular credential kind extends: A -> B -> A"):
        _resolve_kind_with_extends("A", store, ())


def test_cycle_via_outer_entry_c_raises_same_detect():
    """Cycle must be detected when the chain starts outside the cycle (C → A → B → A)."""
    store = {
        "C": _minimal_kind("C", extends="A"),
        "A": _minimal_kind("A", extends="B"),
        "B": _minimal_kind("B", extends="A"),
    }
    with pytest.raises(ValueError, match=r"circular credential kind extends: A -> B -> A"):
        _resolve_kind_with_extends("C", store, ())


def test_self_extend_raises():
    store = {"A": _minimal_kind("A", extends="A")}
    with pytest.raises(ValueError, match=r"circular credential kind extends: A -> A"):
        _resolve_kind_with_extends("A", store, ())
