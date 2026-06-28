from __future__ import annotations

"""Tool Executor node — dispatch a wired tool with explicit arguments."""

import json
import time
from datetime import UTC, datetime
from typing import Any

import analytiq_data as ad

from analytiq_data.flows.agent_loop.dispatch import execute_tool_call
from analytiq_data.flows.agent_loop.types import NormalizedToolCall
from analytiq_data.flows.tool_wiring import WiredToolRegistry


class FlowsToolExecutorNode:
    key = "flows.tool_executor"
    label = "Tool Executor"
    description = "Dispatch a wired tool with explicit arguments — for testing or automation without an LLM."
    category = "AI"
    palette_group = "ai"
    tool_consumer = True
    is_trigger = False
    is_merge = False
    min_inputs = 1
    max_inputs = 1
    outputs = 1
    output_labels = ["output"]
    icon_key = "tool_executor"
    type_version = 1
    experimental = True
    parameter_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "tool_name": {
                "type": "string",
                "description": "Which wired tool to call (must match a wired tool's tool_name parameter).",
                "x-ui-widget": "tool_name_input",
                "x-ui-group": "Tool",
            },
            "arguments_source": {
                "type": "string",
                "enum": ["fixed", "from_input", "input_field"],
                "default": "fixed",
                "x-ui-widget": "select",
                "x-ui-group": "Arguments",
            },
            "arguments": {
                "type": "object",
                "default": {},
                "description": "Fixed arguments object when arguments_source is fixed.",
                "x-ui-widget": "json",
                "x-ui-group": "Arguments",
            },
            "arguments_field": {
                "type": "string",
                "default": "tool_arguments",
                "x-ui-group": "Arguments",
            },
            "mode": {
                "type": "string",
                "enum": ["per_item", "all_items"],
                "default": "per_item",
                "x-ui-widget": "select",
                "x-ui-group": "Options",
            },
        },
        "required": ["tool_name"],
        "additionalProperties": False,
    }

    def validate_parameters(self, params: dict[str, Any]) -> list[str]:
        errs: list[str] = []
        if not str(params.get("tool_name") or "").strip():
            errs.append("parameters.tool_name is required")
        src = params.get("arguments_source") or "fixed"
        if src not in ("fixed", "from_input", "input_field"):
            errs.append("parameters.arguments_source must be fixed, from_input, or input_field")
        return errs

    def _resolve_arguments(self, params: dict[str, Any], item: "ad.flows.FlowItem") -> dict[str, Any]:
        src = params.get("arguments_source") or "fixed"
        if src == "from_input":
            return dict(item.json or {})
        if src == "input_field":
            field = str(params.get("arguments_field") or "tool_arguments")
            raw = (item.json or {}).get(field)
            if not isinstance(raw, dict):
                raise ValueError(f"item.json[{field!r}] must be an object")
            return dict(raw)
        args = params.get("arguments")
        return dict(args) if isinstance(args, dict) else {}

    async def _record_run_data(
        self,
        context: "ad.flows.ExecutionContext",
        *,
        tool_node_id: str,
        output_json: dict[str, Any],
        success: bool,
        start_datetime: datetime,
        elapsed_ms: int,
    ) -> None:
        """Mirror tool dispatch output onto the wired tool_provider node (Path A/B debugging)."""

        from analytiq_data.flows.engine import persist_run_data
        from analytiq_data.flows.trace import pop_node_trace

        context.execution_index += 1
        item = ad.flows.FlowItem(
            json=output_json,
            binary={},
            meta={"dispatched": True},
            paired_item=0,
        )
        context.run_data[tool_node_id] = {
            "status": "success" if success else "error",
            "start_time": start_datetime.isoformat(),
            "execution_time_ms": elapsed_ms,
            "execution_index": context.execution_index,
            "data": {"main": [[item]]},
            "error": None if success else {
                "message": str(output_json.get("error") or "Tool dispatch failed"),
                "node_id": tool_node_id,
                "node_name": None,
                "stack": None,
            },
            "source": [],
            "logs": (context.node_logs.pop(tool_node_id, None) if hasattr(context, "node_logs") else None),
            "trace": pop_node_trace(context, tool_node_id),
        }
        await persist_run_data(
            context,
            context.run_data,
            last_node_executed=tool_node_id,
        )

    async def execute(
        self,
        context: "ad.flows.ExecutionContext",
        node: dict[str, Any],
        inputs: list[list["ad.flows.FlowItem"]],
    ) -> list[list["ad.flows.FlowItem"]]:
        params = node.get("parameters") or {}
        tool_name = str(params.get("tool_name") or "").strip()
        mode = params.get("mode") or "per_item"
        continue_on_fail = (node.get("on_error") or "stop") == "continue"

        wiring = (context.tool_consumer_wiring or {}).get(str(node["id"]))
        if not wiring:
            raise RuntimeError("Tool Executor requires at least one wired tool")
        registry = WiredToolRegistry(wiring)

        in_items = inputs[0] if inputs else []
        if mode == "all_items":
            in_items = in_items[:1]

        out: list["ad.flows.FlowItem"] = []
        upstream_snapshot = ad.flows.materialize_node_data(context.run_data)
        for idx, item in enumerate(in_items):
            dispatch_start = datetime.now(UTC)
            t0 = time.time()
            wired = None
            args: dict[str, Any] = {}
            try:
                wired = registry.resolve(tool_name)
                args = self._resolve_arguments(params, item)
                tc = NormalizedToolCall(id=f"exec-{idx}", name=tool_name, arguments=args)
                raw = await execute_tool_call(
                    tc,
                    wired,
                    context,
                    consumer_node_id=str(node["id"]),
                    parent_item=item,
                    upstream_nodes_snapshot=upstream_snapshot,
                )
                try:
                    tool_result = json.loads(raw)
                except json.JSONDecodeError:
                    tool_result = {"_raw": raw}
                if not isinstance(tool_result, dict):
                    tool_result = {"_raw": tool_result}
                success = True
            except Exception as e:
                if not continue_on_fail:
                    raise
                tool_result = {"error": str(e)}
                args = dict(params.get("arguments") or {}) if isinstance(params.get("arguments"), dict) else {}
                success = False

            elapsed_ms = int((time.time() - t0) * 1000)
            if wired is not None:
                await self._record_run_data(
                    context,
                    tool_node_id=wired.node_id,
                    output_json=tool_result,
                    success=success,
                    start_datetime=dispatch_start,
                    elapsed_ms=elapsed_ms,
                )

            out.append(
                ad.flows.FlowItem(
                    json={
                        "tool_name": tool_name,
                        "arguments": args if success else (params.get("arguments") or {}),
                        "tool_result": tool_result,
                        "success": success,
                    },
                    binary=dict(item.binary or {}),
                    meta={"source_node_id": node["id"], "item_index": idx},
                    paired_item=idx,
                )
            )

        return [out]
