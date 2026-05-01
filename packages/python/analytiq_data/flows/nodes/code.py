from __future__ import annotations

"""Generic code node implementation (`flows.code`)."""

from typing import Any

import analytiq_data as ad


class FlowsCodeNode:
    """
    Execute a small Python snippet against item JSON.

    The snippet runs in a separate Python subprocess with a narrow JSON
    contract. It must define:

        def run(items: list[dict], context: dict) -> list[dict]:
            ...

    The engine calls this once per scheduling step with the full list of
    incoming FlowItems per input slot (`batch_execute_inputs`), unlike nodes
    that resolve parameters once per row.
    """

    key = "flows.code"
    label = "Code (Python)"
    description = "Runs a small Python snippet to transform items."
    category = "Generic"
    is_trigger = False
    is_merge = False
    min_inputs = 1
    max_inputs = 1
    outputs = 1
    output_labels = ["output"]
    icon_key = "code"
    #: When True, ``engine._execute_loop`` invokes ``execute()`` once per work item
    #: with ``inputs`` containing all queued items per slot (n8n-style batch).
    batch_execute_inputs: bool = True
    parameter_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "python_code": {"type": "string"},
            "timeout_seconds": {"type": "number"},
        },
        "required": ["python_code"],
        "additionalProperties": False,
    }

    def validate_parameters(self, params: dict[str, Any]) -> list[str]:
        """Validate code is present and timeout is reasonable."""

        errs: list[str] = []
        if not isinstance(params.get("python_code"), str) or not params["python_code"].strip():
            errs.append("parameters.python_code must be a non-empty string")
        ts = params.get("timeout_seconds")
        if ts is not None:
            try:
                v = float(ts)
                if v <= 0 or v > 30:
                    errs.append("parameters.timeout_seconds must be in (0, 30]")
            except Exception:
                errs.append("parameters.timeout_seconds must be a number")
        return errs

    async def execute(
        self,
        context: "ad.flows.ExecutionContext",
        node: dict[str, Any],
        inputs: list[list["ad.flows.FlowItem"]],
    ) -> list[list["ad.flows.FlowItem"]]:
        """Run the snippet and return transformed items."""

        params = node.get("parameters") or {}
        code = params["python_code"]
        timeout_seconds = float(params.get("timeout_seconds") or 2.0)

        in_items = inputs[0]
        payload_items = [it.json for it in in_items]
        probe = in_items[0] if in_items else None
        src_start, src_exec_ms = ad.flows.timing_from_items_source_run(probe, context.run_data)
        ctx = {
            "trigger": context.trigger_data,
            "node_id": node.get("id"),
            "mode": context.mode,
            "nodes": ad.flows.materialize_node_data(context.run_data),
            "organization_id": context.organization_id,
            "execution_id": context.execution_id,
            "flow_id": context.flow_id,
            "flow_revid": context.flow_revid,
            "start_time": src_start,
            "execution_time": src_exec_ms,
        }

        out_json_items = await ad.flows.run_python_code(
            code=code,
            items=payload_items,
            context=ctx,
            timeout_seconds=timeout_seconds,
        )

        out: list["ad.flows.FlowItem"] = []
        for idx, j in enumerate(out_json_items):
            src = None
            if in_items:
                src = in_items[min(idx, len(in_items) - 1)]
            merged_bin = dict(src.binary) if src is not None else {}
            out.append(
                ad.flows.FlowItem(
                    json=j,
                    binary=merged_bin,
                    meta={"source_node_id": node["id"], "item_index": idx},
                    paired_item=None,
                )
            )
        return [out]

