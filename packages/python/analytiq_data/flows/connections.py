from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypedDict

ConnectionType = Literal["main"]


@dataclass
class NodeConnection:
    node: str
    type: ConnectionType
    index: int


NodeOutputSlots = list[list[NodeConnection] | None]


class NodeConnections(TypedDict, total=False):
    main: NodeOutputSlots


Connections = dict[str, NodeConnections]

