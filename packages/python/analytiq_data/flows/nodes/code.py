from __future__ import annotations

"""Generic code node implementation (`flows.code`)."""

from typing import Any

import analytiq_data as ad


class FlowsCodeNode:
    """
    Execute Python user code in an isolated subprocess.

    User code must define::

        def run(items: list[dict], context: dict) -> list[dict]:
            ...

    Mode controls whether ``run`` is invoked once for all items or once per item inside the child.

    The engine calls ``execute()`` once with all upstream items (``batch_execute_inputs``).
    """

    key = "flows.code"
    label = "Code (Python)"
    description = "Runs a small Python snippet to transform items."
    category = "Generic"
    palette_group = "core"
    is_trigger = False
    is_merge = False
    min_inputs = 1
    max_inputs = 1
    outputs = 1
    output_labels = ["output"]
    icon_key = "code"
    type_version = 2
    batch_execute_inputs: bool = True
    parameter_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "mode": {
                "type": "string",
                "enum": ["all_items", "per_item"],
                "default": "all_items",
                "description": "Run once for all input items, or once per item.",
                "x-ui-widget": "select",
                "x-ui-group": "Options",
            },
            "python_code": {
                "type": "string",
                "minLength": 1,
                "default": "def run(items, context):\n  return items\n",
                "description": "Must define def run(items: list[dict], context: dict) -> list[dict].",
                "x-ui-widget": "code",
                "x-ui-group": "Code",
            },
            "timeout_seconds": {
                "type": "number",
                "default": 30,
                "minimum": 0.0001,
                "maximum": 120,
                "description": "Subprocess wall-clock limit in seconds (default 30, max 120).",
                "x-ui-group": "Options",
                "x-ui-placeholder": "e.g. 30",
            },
        },
        "required": ["python_code"],
        "additionalProperties": False,
    }

    def validate_parameters(self, params: dict[str, Any]) -> list[str]:
        errs: list[str] = []
        mode = params.get("mode", "all_items")
        if mode not in ("all_items", "per_item"):
            errs.append("parameters.mode must be 'all_items' or 'per_item'")
        if not isinstance(params.get("python_code"), str) or not params["python_code"].strip():
            errs.append("parameters.python_code must be a non-empty string")
        ts = params.get("timeout_seconds")
        if ts is not None:
            try:
                v = float(ts)
                if v <= 0 or v > 120:
                    errs.append("parameters.timeout_seconds must be in (0, 120]")
            except Exception:
                errs.append("parameters.timeout_seconds must be a number")
        return errs

    async def execute(
        self,
        context: "ad.flows.ExecutionContext",
        node: dict[str, Any],
        inputs: list[list["ad.flows.FlowItem"]],
    ) -> list[list["ad.flows.FlowItem"]]:
        params = node.get("parameters") or {}
        code = params["python_code"]
        mode = params.get("mode") or "all_items"
        timeout_seconds = float(params.get("timeout_seconds") or 30.0)
        continue_on_fail = (node.get("on_error") or "stop") == "continue"

        in_items = inputs[0]
        payload_items = [ad.flows.flow_item_to_sandbox_dict(it) for it in in_items]
        probe = in_items[0] if in_items else None
        src_start, src_exec_ms = ad.flows.timing_from_items_source_run(probe, context.run_data)
        ctx = {
            "trigger": context.trigger_data,
            "node_id": node.get("id"),
            "node_name": node.get("name"),
            "mode": context.mode,
            "nodes": ad.flows.materialize_node_data(context.run_data),
            "organization_id": context.organization_id,
            "execution_id": context.execution_id,
            "flow_id": context.flow_id,
            "flow_revid": context.flow_revid,
            "start_time": src_start,
            "execution_time": src_exec_ms,
        }

        out_items, logs = await ad.flows.run_python_code(
            code=code,
            items=payload_items,
            context=ctx,
            mode=mode,
            timeout_seconds=timeout_seconds,
            continue_on_fail=continue_on_fail,
            analytiq_client=context.analytiq_client,
            node_id=str(node.get("id") or ""),
            execution_id=str(context.execution_id or ""),
        )

        if logs:
            nid = str(node.get("id") or "")
            if nid:
                try:
                    context.node_logs[nid] = [str(x) for x in logs]
                except Exception:
                    pass

        out: list["ad.flows.FlowItem"] = []
        for idx, item in enumerate(out_items):
            json_payload = item.get("json") if isinstance(item.get("json"), dict) else {}
            binary_raw = item.get("binary") if isinstance(item.get("binary"), dict) else {}
            meta = dict(item.get("meta") or {})
            meta.setdefault("source_node_id", node["id"])
            meta.setdefault("item_index", idx)
            binary = {
                k: ad.flows.coerce_binary_ref(v) for k, v in binary_raw.items()
            }
            out.append(
                ad.flows.FlowItem(
                    json=json_payload,
                    binary=binary,
                    meta=meta,
                    paired_item=item.get("paired_item"),
                )
            )
        return [out]
