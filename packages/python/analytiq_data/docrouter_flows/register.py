from __future__ import annotations

"""Register DocRouter node types into the global `analytiq_data.flows` registry."""

import analytiq_data as ad

from .nodes import (
    DocRouterLlmExtractNode,
    DocRouterManualTriggerNode,
    DocRouterOcrNode,
    DocRouterSetTagsNode,
)


def register_docrouter_nodes() -> None:
    """Register all DocRouter-provided node type instances (idempotent by key)."""

    ad.flows.register(DocRouterManualTriggerNode())
    ad.flows.register(DocRouterOcrNode())
    ad.flows.register(DocRouterLlmExtractNode())
    ad.flows.register(DocRouterSetTagsNode())
