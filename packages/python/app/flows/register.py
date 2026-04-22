from __future__ import annotations

import analytiq_data as ad

from .nodes import (
    DocRouterManualTriggerNode,
    DocRouterOcrNode,
    DocRouterLlmExtractNode,
    DocRouterSetTagsNode,
)


def register_docrouter_nodes() -> None:
    ad.flows.register(DocRouterManualTriggerNode())
    ad.flows.register(DocRouterOcrNode())
    ad.flows.register(DocRouterLlmExtractNode())
    ad.flows.register(DocRouterSetTagsNode())

