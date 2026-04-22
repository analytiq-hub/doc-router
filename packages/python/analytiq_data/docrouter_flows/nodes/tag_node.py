from __future__ import annotations

"""DocRouter node implementation that applies tags to documents."""

from typing import Any

import analytiq_data as ad

from .. import services as flow_services


class DocRouterSetTagsNode:
    """Apply a configured list of tag ids to each input document item."""

    key = "docrouter.set_tags"
    label = "Set tags"
    description = "Applies configured tags."
    category = "DocRouter"
    is_trigger = False
    min_inputs = 1
    max_inputs = 1
    outputs = 1
    output_labels = ["output"]
    parameter_schema: dict[str, Any] = {
        "type": "object",
        "properties": {"tag_ids": {"type": "array", "items": {"type": "string"}}},
        "required": ["tag_ids"],
        "additionalProperties": False,
    }

    def validate_parameters(self, params: dict[str, Any]) -> list[str]:
        """Require `tag_ids` to be a list."""

        if not isinstance(params.get("tag_ids"), list):
            return ["parameters.tag_ids must be a list of strings"]
        return []

    async def execute(
        self,
        context: "ad.flows.ExecutionContext",
        node: dict[str, Any],
        inputs: list[list["ad.flows.FlowItem"]],
    ):
        """Update tags in storage and reflect them in the outgoing item JSON."""

        tag_ids: list[str] = (node.get("parameters") or {}).get("tag_ids") or []
        out: list["ad.flows.FlowItem"] = []
        for it in inputs[0]:
            doc_id = it.json.get("document_id") or (it.json.get("document") or {}).get("_id")
            if not doc_id:
                raise ValueError("Input item missing document_id")
            await flow_services.set_tags(context.analytiq_client, context.organization_id, doc_id, tag_ids)
            merged = dict(it.json)
            merged["tag_ids"] = tag_ids
            out.append(
                ad.flows.FlowItem(
                    json=merged, binary=it.binary, meta=it.meta, paired_item=it.paired_item
                )
            )
        return [out]
