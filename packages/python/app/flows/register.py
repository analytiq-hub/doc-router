from __future__ import annotations

"""DocRouter flow node registration helpers."""

import analytiq_data as ad

from .nodes import (
    DocRouterManualTriggerNode,
    DocRouterOcrNode,
    DocRouterLlmExtractNode,
    DocRouterSetTagsNode,
)


def register_docrouter_nodes() -> None:
    """Register all DocRouter-provided node types into the global `ad.flows` registry."""

    ad.flows.register(DocRouterManualTriggerNode())
    ad.flows.register(DocRouterOcrNode())
    ad.flows.register(DocRouterLlmExtractNode())
    ad.flows.register(DocRouterSetTagsNode())

