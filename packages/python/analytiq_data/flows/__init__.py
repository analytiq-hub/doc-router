"""
Generic flow engine (DocRouter-independent).

See `docs/flows.md` for the v1 spec and semantics.
"""

from .items import FlowItem, BinaryRef
from .connections import NodeConnection, ConnectionType, Connections
from .context import ExecutionContext, ExecutionMode, FlowServices
from .execution import NodeRunData, NodeOutputData
from .node_registry import NodeType, register, get, list_all
from .engine import FlowEngine, FlowValidationError
from .register_builtin import register_builtin_nodes

