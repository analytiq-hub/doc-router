from __future__ import annotations

import analytiq_data as ad


def register_builtin_nodes() -> None:
    ad.flows.register(ad.flows.FlowsManualTriggerNode())
    ad.flows.register(ad.flows.FlowsWebhookTriggerNode())
    ad.flows.register(ad.flows.FlowsRespondToWebhookNode())
    ad.flows.register(ad.flows.FlowsHttpRequestNode())
    ad.flows.register(ad.flows.FlowsBranchNode())
    ad.flows.register(ad.flows.FlowsMergeNode())
    ad.flows.register(ad.flows.FlowsCodeNode())

