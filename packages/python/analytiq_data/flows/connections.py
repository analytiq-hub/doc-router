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


NodeOutputSlots = list[list[NodeConnection] | None]


class NodeConnections(TypedDict, total=False):
    main: NodeOutputSlots


Connections = dict[str, NodeConnections]

