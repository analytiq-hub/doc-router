from __future__ import annotations

"""AI Agent node — LLM tool-calling loop adapter (`flows.agent`)."""

from typing import Any

import analytiq_data as ad

from analytiq_data.flows.agent_loop import FlowAgentConfig, FlowAgentLoop
from analytiq_data.flows.agent_loop.messages import DEFAULT_SYSTEM_MESSAGE, build_all_items_user_message, build_user_message
from analytiq_data.flows.tool_wiring import WiredToolRegistry


class FlowsAgentNode:
    key = "flows.agent"
    label = "AI Agent"
    description = "Orchestrates an LLM tool-calling loop with wired tools."
    category = "AI"
    palette_group = "ai"
    tool_consumer = True
    is_trigger = False
    is_merge = False
    min_inputs = 1
    max_inputs = 1
    outputs = 1
    output_labels = ["output"]
    icon_key = "agent"
    type_version = 1
    experimental = True
    parameter_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "prompt_source": {
                "title": "Prompt source",
                "description": (
                    "Where the user message comes from. From input reads a field on each inbound item; "
                    "Fixed uses Prompt text; Chat trigger uses chatInput from a Chat Trigger upstream."
                ),
                "type": "string",
                "enum": ["from_input", "fixed", "chat_trigger"],
                "default": "from_input",
                "x-ui-widget": "select",
                "x-ui-enum-names": ["From input", "Fixed", "Chat trigger"],
                "x-ui-group": "Prompt",
            },
            "prompt_text": {
                "title": "Prompt text",
                "description": (
                    "User message sent to the model when Prompt source is Fixed. Supports = expressions."
                ),
                "type": "string",
                "x-ui-widget": "textarea",
                "x-ui-show-when": {"field": "prompt_source", "equals": "fixed"},
                "x-ui-group": "Prompt",
            },
            "prompt_field": {
                "title": "Prompt field",
                "description": (
                    "JSON key on the inbound item to use as the user message when Prompt source is From input "
                    "(default: query)."
                ),
                "type": "string",
                "default": "query",
                "x-ui-show-when": {"field": "prompt_source", "equals": "from_input"},
                "x-ui-group": "Prompt",
            },
            "system_message": {
                "title": "System message",
                "description": (
                    "System-role instructions for every agent run (persona, tool-use rules, tone). "
                    "Not the end-user question — that comes from Prompt source."
                ),
                "type": "string",
                "default": DEFAULT_SYSTEM_MESSAGE,
                "x-ui-widget": "textarea",
                "x-ui-group": "Prompt",
            },
            "model": {
                "title": "Model",
                "description": "LiteLLM model id enabled for your organization.",
                "x-ui-widget": "llm_model_picker",
                "x-ui-group": "Model",
            },
            "temperature": {
                "title": "Temperature",
                "description": (
                    "Sampling randomness for the model. Lower values (e.g. 0.2) are more focused and "
                    "deterministic; higher values are more varied. Range 0–2."
                ),
                "type": "number",
                "default": 0.2,
                "minimum": 0,
                "maximum": 2,
                "x-ui-group": "Model",
            },
            "max_tool_rounds": {
                "title": "Max tool rounds",
                "description": (
                    "Maximum number of LLM ↔ tool-call iterations before the agent stops. Caps runaway "
                    "loops when the model keeps invoking tools. Range 1–20."
                ),
                "type": "integer",
                "default": 10,
                "minimum": 1,
                "maximum": 20,
                "x-ui-group": "Options",
            },
            "mode": {
                "title": "Mode",
                "description": (
                    "Per item runs one agent call for each inbound row. All items combines every row's "
                    "JSON into a single prompt and produces one output row."
                ),
                "type": "string",
                "enum": ["per_item", "all_items"],
                "default": "per_item",
                "x-ui-widget": "select",
                "x-ui-enum-names": ["Per item", "All items"],
                "x-ui-group": "Options",
            },
            "response_field": {
                "title": "Response field",
                "description": (
                    "JSON key on each output item where the agent's final text reply is written "
                    "(default: agent_output)."
                ),
                "type": "string",
                "default": "agent_output",
                "x-ui-group": "Output",
            },
            "include_tool_trace": {
                "title": "Include tool trace",
                "description": (
                    "When enabled, adds agent_tool_calls to the output with each tool name, arguments, "
                    "result preview, duration, and success flag."
                ),
                "type": "boolean",
                "default": True,
                "x-ui-group": "Output",
            },
            "enable_streaming": {
                "title": "Enable streaming",
                "description": (
                    "Auto follows the execution context (e.g. streams in chat). Force on always streams "
                    "when the model supports it; force off waits for the full reply before continuing."
                ),
                "type": "string",
                "enum": ["auto", "true", "false"],
                "default": "auto",
                "x-ui-widget": "select",
                "x-ui-enum-names": ["Auto", "On", "Off"],
                "x-ui-group": "Output",
            },
        },
        "additionalProperties": False,
    }

    def validate_parameters(self, params: dict[str, Any]) -> list[str]:
        errs: list[str] = []
        if not str(params.get("model") or "").strip():
            errs.append("parameters.model is required")
        rounds = params.get("max_tool_rounds", 10)
        try:
            r = int(rounds)
            if r < 1 or r > 20:
                errs.append("parameters.max_tool_rounds must be between 1 and 20")
        except Exception:
            errs.append("parameters.max_tool_rounds must be an integer")
        return errs

    def _resolve_streaming(self, params: dict[str, Any], context: "ad.flows.ExecutionContext") -> bool:
        raw = params.get("enable_streaming", "auto")
        if raw is True or raw == "true":
            return True
        if raw is False or raw == "false":
            return False
        return bool(context.is_streaming)

    async def execute(
        self,
        context: "ad.flows.ExecutionContext",
        node: dict[str, Any],
        inputs: list[list["ad.flows.FlowItem"]],
    ) -> list[list["ad.flows.FlowItem"]]:
        params = node.get("parameters") or {}
        mode = params.get("mode") or "per_item"
        response_field = str(params.get("response_field") or "agent_output")
        include_trace = bool(params.get("include_tool_trace", True))
        continue_on_fail = (node.get("on_error") or "stop") == "continue"
        system_message = str(params.get("system_message") or DEFAULT_SYSTEM_MESSAGE).strip() or DEFAULT_SYSTEM_MESSAGE
        model = str(params.get("model") or "").strip()
        temperature = float(params.get("temperature") if params.get("temperature") is not None else 0.2)
        max_rounds = int(params.get("max_tool_rounds") or 10)
        enable_streaming = self._resolve_streaming(params, context)

        wiring = (context.tool_consumer_wiring or {}).get(str(node["id"]), [])
        registry = WiredToolRegistry(wiring)

        in_items = inputs[0] if inputs else []
        out: list["ad.flows.FlowItem"] = []
        upstream_snapshot = ad.flows.materialize_node_data(context.run_data)

        async def _run_one(item: "ad.flows.FlowItem", *, user_message: str) -> "ad.flows.FlowItem":
            loop = FlowAgentLoop(
                analytiq_client=context.analytiq_client,
                organization_id=context.organization_id,
                execution_context=context,
                tool_registry=registry,
                consumer_node_id=str(node["id"]),
                parent_item=item,
                upstream_nodes_snapshot=upstream_snapshot,
                trigger_snapshot=dict(item.json or {}),
            )
            config = FlowAgentConfig(
                model=model,
                system_message=system_message,
                user_message=user_message,
                max_tool_rounds=max_rounds,
                temperature=temperature,
                enable_streaming=enable_streaming,
            )
            result = await loop.run(config)
            if result.error and not continue_on_fail:
                raise RuntimeError(result.error)

            payload: dict[str, Any] = {
                response_field: result.text,
                "max_rounds_reached": result.max_rounds_reached,
            }
            if result.error:
                payload["agent_error"] = result.error
            if include_trace:
                payload["agent_tool_calls"] = [
                    {
                        "round": t.round,
                        "tool": t.tool,
                        "arguments": t.arguments,
                        "result_preview": t.result_preview,
                        "duration_ms": t.duration_ms,
                        "success": t.success,
                        **({"error": t.error} if t.error else {}),
                    }
                    for t in result.tool_calls
                ]
            return ad.flows.FlowItem(
                json=payload,
                binary=dict(item.binary or {}),
                meta={"source_node_id": node["id"]},
                paired_item=item.paired_item,
            )

        if mode == "all_items":
            user_message = build_all_items_user_message([it.json for it in in_items])
            # all_items: one LLM run over every item's json; binary is not included in the prompt.
            # Use the first item only for paired_item / binary passthrough on the output row
            # (synthetic empty item when there are no inputs — intentional).
            item = in_items[0] if in_items else ad.flows.FlowItem(json={}, binary={}, meta={})
            out.append(await _run_one(item, user_message=user_message))
        else:
            for idx, item in enumerate(in_items):
                user_message = build_user_message(
                    item.json,
                    prompt_source=str(params.get("prompt_source") or "from_input"),
                    prompt_field=str(params.get("prompt_field") or "query"),
                    prompt_text=str(params.get("prompt_text") or ""),
                )
                row = await _run_one(item, user_message=user_message)
                row.paired_item = idx
                out.append(row)

        return [out]
