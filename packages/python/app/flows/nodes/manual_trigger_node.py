from __future__ import annotations

"""DocRouter node implementation for manual document-triggered flows."""

from typing import Any

import analytiq_data as ad


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
    parameter_schema: dict[str, Any] = {
        "type": "object",
        "properties": {"document_id": {"type": "string"}},
        "required": ["document_id"],
        "additionalProperties": False,
    }

    def validate_parameters(self, params: dict[str, Any]) -> list[str]:
        """Require a `document_id` parameter for manual document runs."""

        if not isinstance(params.get("document_id"), str) or not params["document_id"]:
            return ["parameters.document_id is required"]
        return []

    async def execute(
        self,
        context: "ad.flows.ExecutionContext",
        node: dict[str, Any],
        inputs: list[list["ad.flows.FlowItem"]],
    ):
        """Fetch the document and emit it as `json.document` + `json.document_id`."""

        doc_id = (node.get("parameters") or {}).get("document_id") or context.trigger_data.get("document_id")
        if not doc_id:
            raise ValueError("document_id required for docrouter.trigger.manual")
        doc = await context.services.get_document(context.organization_id, doc_id)
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

