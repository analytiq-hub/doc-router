from __future__ import annotations

"""DocRouter flow node registration helpers."""

import analytiq_data as ad

def register_docrouter_nodes() -> None:
    """Register all DocRouter-provided node types into the global `ad.flows` registry."""

    ad.flows.register(ad.flows.DocRouterManualTriggerNode())
    ad.flows.register(ad.flows.DocRouterOcrNode())
    ad.flows.register(ad.flows.DocRouterLlmExtractNode())
    ad.flows.register(ad.flows.DocRouterSetTagsNode())

