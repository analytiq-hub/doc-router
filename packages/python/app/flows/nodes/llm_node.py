from __future__ import annotations

"""DocRouter node implementation that runs a prompt-based LLM extraction."""

from typing import Any

import analytiq_data as ad


class DocRouterLlmExtractNode:
    """Execute a configured prompt+schema extraction for each input document item."""

    key = "docrouter.llm_extract"
    label = "LLM extract"
    description = "Runs linked prompt-based extraction."
    category = "DocRouter"
    is_trigger = False
    min_inputs = 1
    max_inputs = 1
    outputs = 1
    output_labels = ["output"]
    parameter_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "prompt_id": {"type": "string"},
            "schema_id": {"type": "string"},
        },
        "required": ["prompt_id", "schema_id"],
        "additionalProperties": False,
    }

    def validate_parameters(self, params: dict[str, Any]) -> list[str]:
        """Require both `prompt_id` and `schema_id` parameters for v1 extraction."""

        errs = []
        if not isinstance(params.get("prompt_id"), str) or not params["prompt_id"]:
            errs.append("parameters.prompt_id is required")
        if not isinstance(params.get("schema_id"), str) or not params["schema_id"]:
            errs.append("parameters.schema_id is required")
        return errs

    async def execute(
        self,
        context: "ad.flows.ExecutionContext",
        node: dict[str, Any],
        inputs: list[list["ad.flows.FlowItem"]],
    ):
        """Run extraction and attach results under `json.llm_extract`."""

        params = node.get("parameters") or {}
        prompt_id = params["prompt_id"]
        schema_id = params["schema_id"]
        out: list["ad.flows.FlowItem"] = []
        for it in inputs[0]:
            doc_id = it.json.get("document_id") or (it.json.get("document") or {}).get("_id")
            if not doc_id:
                raise ValueError("Input item missing document_id")
            res = await context.services.run_llm_extract(context.organization_id, doc_id, prompt_id, schema_id)
            merged = dict(it.json)
            merged["llm_extract"] = res
            out.append(
                ad.flows.FlowItem(
                    json=merged, binary=it.binary, meta=it.meta, paired_item=it.paired_item
                )
            )
        return [out]

