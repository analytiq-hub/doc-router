from __future__ import annotations

"""
Connection typing for flow revisions.

The connections adjacency map is keyed by *source* node id. Each `NodeConnection`
describes a fan-out edge to a *destination* node input port.
"""

from dataclasses import dataclass
from typing import TypedDict

# Allowed values (v1): "main"
# Future (reserved): "error_output", ...


@dataclass
class NodeConnection:
    """One edge from a source output slot to a destination input slot."""

    dest_node_id: str
    connection_type: str
    index: int

class NodeConnections(TypedDict, total=False):
    """Typed per-source adjacency entry. Keys are optional (`total=False`)."""

    main: list[list[NodeConnection] | None]


Connections = dict[str, NodeConnections]

