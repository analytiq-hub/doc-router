"""Tests for agent dispatch helpers."""

from __future__ import annotations

from analytiq_data.flows.agent_loop.dispatch import _cap_nodes_snapshot


def test_cap_nodes_snapshot_trims_incrementally() -> None:
    nodes = {f"n{i}": {"payload": "x" * 4000} for i in range(50)}
    capped = _cap_nodes_snapshot(nodes)
    assert len(capped) < len(nodes)
    assert capped
    for key in capped:
        assert key in nodes
