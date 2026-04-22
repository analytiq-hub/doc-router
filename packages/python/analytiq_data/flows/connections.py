from __future__ import annotations

"""
Connection typing for flow revisions.

The connections adjacency map is keyed by *source* node id. Each `NodeConnection`
describes a fan-out edge to a *destination* node input port.
"""

from dataclasses import dataclass
from typing import Any, Literal, TypedDict

@dataclass
class NodeConnection:
    """One edge from a source output slot to a destination input slot."""

    dest_node_id: str
    connection_type: Literal["main"]
    index: int

class NodeConnections(TypedDict, total=False):
    """Typed per-source adjacency entry. Keys are optional (`total=False`)."""

    main: list[list[NodeConnection] | None]


Connections = dict[str, NodeConnections]


def coerce_json_connections_to_dataclasses(raw: dict[str, Any] | None) -> "Connections":
    """
    Coerce a JSON / Mongo-stored connection map to `NodeConnection` instances.

    HTTP save paths and `run_flow` on revisions loaded from the database use this shape; the
    engine requires dataclass edges for validation and execution.
    """

    out: Connections = {}
    for src, typed in (raw or {}).items():
        out[src] = {}
        main_slots = (typed or {}).get("main") or []
        slots: list[list[NodeConnection] | None] = []
        for slot in main_slots:
            if slot is None:
                slots.append(None)
                continue
            conns: list[NodeConnection] = []
            for c in slot:
                if c is None:
                    continue
                if isinstance(c, NodeConnection):
                    conns.append(c)
                    continue
                dest_node_id = c.get("dest_node_id") or c.get("node_id") or c.get("node")
                if not dest_node_id:
                    raise ValueError("Connection missing dest_node_id")
                conns.append(
                    NodeConnection(
                        dest_node_id=dest_node_id,
                        connection_type="main",
                        index=int(c["index"]),
                    )
                )
            slots.append(conns)
        out[src]["main"] = slots
    return out

