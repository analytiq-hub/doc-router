from __future__ import annotations

from .node_registry import register
from .nodes import FlowsManualTriggerNode, FlowsWebhookNode, FlowsBranchNode, FlowsMergeNode


def register_builtin_nodes() -> None:
    register(FlowsManualTriggerNode())
    register(FlowsWebhookNode())
    register(FlowsBranchNode())
    register(FlowsMergeNode())

