from __future__ import annotations

"""DocRouter node implementation for manual document-triggered flows."""

from typing import Any

import analytiq_data as ad

from .. import services as flow_services


class DocRouterManualTriggerNode:
    """Trigger node that emits a single item containing the target document payload."""

    key = "docrouter.trigger.manual"
    label = "Manual trigger (document)"
    description = "Emits the target document as one item."
    category = "DocRouter"
    is_trigger = True
    min_inputs = 0
    max_inputs = 0
    outputs = 1
    output_labels = ["output"]
    # Triggers have no user-editable parameters; `document_id` comes from the run request / trigger_data.
    parameter_schema: dict[str, Any] = {
        "type": "object",
        "properties": {},
        "additionalProperties": True,
    }

    def validate_parameters(self, params: dict[str, Any]) -> list[str]:
        return []

    async def execute(
        self,
        context: "ad.flows.ExecutionContext",
        node: dict[str, Any],
        inputs: list[list["ad.flows.FlowItem"]],
    ):
        """Fetch the document and emit it as `json.document` + `json.document_id`."""

        doc_id = context.trigger_data.get("document_id")
        if not isinstance(doc_id, str) or not doc_id.strip():
            raise ValueError("document_id required in trigger_data for docrouter.trigger.manual")
        doc = await flow_services.get_document(context.analytiq_client, context.organization_id, doc_id)
        return [
            [
                ad.flows.FlowItem(
                    json={"document": doc, "document_id": doc_id},
                    binary={},
                    meta={"source_node_id": node["id"], "item_index": 0},
                    paired_item=None,
                )
            ]
        ]
