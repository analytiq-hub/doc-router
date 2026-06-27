from __future__ import annotations

"""Execute another flow's active revision (n8n Execute Workflow parity)."""

from typing import Any

import analytiq_data as ad
from analytiq_data.flows.sub_flow import SubFlowError, run_nested_subflow, resolve_subflow_return_items


class FlowsExecuteFlowNode:
    key = "flows.execute_flow"
    label = "Execute Flow"
    description = (
        "Runs another flow's active revision and returns the last executed node's output "
        "(like n8n Execute Workflow)."
    )
    category = "Generic"
    palette_group = "flow"
    is_trigger = False
    is_merge = False
    min_inputs = 1
    max_inputs = 1
    outputs = 1
    output_labels = ["output"]
    icon_key = "execute_flow"
    type_version = 1
    experimental = True
    parameter_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "target_flow_id": {
                "type": "string",
                "x-ui-widget": "flow_picker",
                "x-ui-flow-picker-mode": "subflow",
                "x-ui-group": "Flow",
            },
            "mode": {
                "type": "string",
                "enum": ["each", "once"],
                "default": "each",
                "x-ui-group": "Flow",
            },
        },
        "required": ["target_flow_id"],
        "additionalProperties": False,
    }

    def validate_parameters(self, params: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        if not str(params.get("target_flow_id") or "").strip():
            errors.append("target_flow_id is required")
        return errors

    async def execute(
        self,
        context: "ad.flows.ExecutionContext",
        node: dict[str, Any],
        inputs: list[list["ad.flows.FlowItem"]],
    ) -> list[list["ad.flows.FlowItem"]]:
        params = node.get("parameters") or {}
        target_flow_id = str(params.get("target_flow_id") or "").strip()
        mode = str(params.get("mode") or "each")
        inbound = inputs[0] if inputs else []
        if not inbound:
            return [[]]

        out: list[ad.flows.FlowItem] = []

        async def _run_one(trigger_payload: dict[str, Any]) -> None:
            run = await run_nested_subflow(
                parent_ctx=context,
                target_flow_id=target_flow_id,
                trigger_data=trigger_payload,
                require_callable_as_tool=False,
                mode="sub_flow",
            )
            out.extend(resolve_subflow_return_items(run))

        try:
            if mode == "once":
                payload = {
                    "subflow_input": {
                        "items": [
                            it.json if isinstance(it.json, dict) else {"value": it.json} for it in inbound
                        ]
                    }
                }
                await _run_one(payload)
            else:
                for item in inbound:
                    j = item.json
                    payload = {
                        "subflow_input": dict(j) if isinstance(j, dict) else {"value": j},
                    }
                    await _run_one(payload)
        except SubFlowError as e:
            raise ValueError(str(e)) from e

        return [out]
