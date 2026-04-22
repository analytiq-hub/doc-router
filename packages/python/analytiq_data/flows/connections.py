from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict

# Allowed values (v1): "main"
# Future (reserved): "error_output", ...


@dataclass
class NodeConnection:
    dest_node_id: str
    connection_type: str
    index: int

class NodeConnections(TypedDict, total=False):
    main: list[list[NodeConnection] | None]


Connections = dict[str, NodeConnections]

