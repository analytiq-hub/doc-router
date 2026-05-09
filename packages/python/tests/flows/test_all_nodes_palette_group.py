"""Every registered node type must resolve to a known picker section key."""

from __future__ import annotations

import analytiq_data as ad
from analytiq_data.flows.palette_groups import PALETTE_GROUP_KEYS, resolve_palette_group


def test_registered_node_types_resolve_to_allowed_palette_groups() -> None:
    ad.flows.register_builtin_nodes()
    ad.flows.register_docrouter_nodes()

    allowed = frozenset(PALETTE_GROUP_KEYS)
    for nt in ad.flows.list_all():
        resolved = resolve_palette_group(nt)
        assert resolved in allowed, f"{nt.key!r}: resolve_palette_group → {resolved!r}, expected one of {sorted(allowed)}"
