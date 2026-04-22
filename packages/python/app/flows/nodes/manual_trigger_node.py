from __future__ import annotations

from typing import Any

from analytiq_data.flows.context import ExecutionContext
from analytiq_data.flows.items import FlowItem


class DocRouterManualTriggerNode:
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
        if not isinstance(params.get("document_id"), str) or not params["document_id"]:
            return ["parameters.document_id is required"]
        return []

    async def execute(self, context: ExecutionContext, node: dict[str, Any], inputs: list[list[FlowItem]]):
        doc_id = (node.get("parameters") or {}).get("document_id") or context.trigger_data.get("document_id")
        if not doc_id:
            raise ValueError("document_id required for docrouter.trigger.manual")
        doc = await context.services.get_document(context.organization_id, doc_id)
        return [
            [
                FlowItem(
                    json={"document": doc, "document_id": doc_id},
                    binary={},
                    meta={"source_node_id": node["id"], "item_index": 0},
                    paired_item=None,
                )
            ]
        ]

