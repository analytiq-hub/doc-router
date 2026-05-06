from __future__ import annotations

import analytiq_data as ad


def test_finalized_dirty_always_adds_execute_step_target() -> None:
    known = frozenset({"t1", "u1", "c1"})
    assert ad.flows.finalized_dirty_node_ids(
        dirty_node_ids=[],
        target_node_id="c1",
        known_node_ids=known,
    ) == ["c1"]


def test_finalized_dirty_sorts_unions_client_dirty_with_target() -> None:
    known = frozenset({"a", "z", "mid"})
    assert ad.flows.finalized_dirty_node_ids(
        dirty_node_ids=["z", "mid"],
        target_node_id="mid",
        known_node_ids=known,
    ) == ["mid", "z"]


def test_finalized_dirty_drops_unknown_ids() -> None:
    known = frozenset({"only"})
    assert ad.flows.finalized_dirty_node_ids(
        dirty_node_ids=["ghost", "only"],
        target_node_id="ghost",
        known_node_ids=known,
    ) == ["only"]
