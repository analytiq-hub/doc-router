from __future__ import annotations

from analytiq_data.flows.node_registry import register

from .nodes import (
    DocRouterManualTriggerNode,
    DocRouterOcrNode,
    DocRouterLlmExtractNode,
    DocRouterSetTagsNode,
)


def register_docrouter_nodes() -> None:
    register(DocRouterManualTriggerNode())
    register(DocRouterOcrNode())
    register(DocRouterLlmExtractNode())
    register(DocRouterSetTagsNode())

