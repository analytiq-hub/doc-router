from __future__ import annotations

"""Register DocRouter node types into the global `analytiq_data.flows` registry."""

import analytiq_data as ad

from .nodes import (
    DocRouterEventTriggerNode,
    DocRouterLlmRunNode,
    DocRouterOcrNode,
)


def register_docrouter_nodes() -> None:
    """Register all DocRouter-provided node type instances (idempotent by key)."""

    ad.flows.register(DocRouterEventTriggerNode())
    ad.flows.register(DocRouterOcrNode())
    ad.flows.register(DocRouterLlmRunNode())
