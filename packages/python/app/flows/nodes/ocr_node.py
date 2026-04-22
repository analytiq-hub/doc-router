from __future__ import annotations

from typing import Any

from analytiq_data.flows.context import ExecutionContext
from analytiq_data.flows.items import FlowItem


class DocRouterOcrNode:
    key = "docrouter.ocr"
    label = "Run OCR"
    description = "Runs OCR on the input document(s)."
    category = "DocRouter"
    is_trigger = False
    min_inputs = 1
    max_inputs = 1
    outputs = 1
    output_labels = ["output"]
    parameter_schema: dict[str, Any] = {"type": "object", "properties": {}, "additionalProperties": False}

    def validate_parameters(self, params: dict[str, Any]) -> list[str]:
        return []

    async def execute(self, context: ExecutionContext, node: dict[str, Any], inputs: list[list[FlowItem]]):
        out: list[FlowItem] = []
        for it in inputs[0]:
            doc_id = it.json.get("document_id") or (it.json.get("document") or {}).get("_id")
            if not doc_id:
                raise ValueError("Input item missing document_id")
            result = await context.services.run_ocr(context.organization_id, doc_id)
            merged = dict(it.json)
            merged["ocr"] = result
            out.append(
                FlowItem(json=merged, binary=it.binary, meta=it.meta, paired_item=it.paired_item)
            )
        return [out]

