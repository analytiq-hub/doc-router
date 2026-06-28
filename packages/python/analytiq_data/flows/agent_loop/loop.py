"""Flow agent tool-calling loop."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

import analytiq_data as ad

from analytiq_data.flows.agent_loop import billing
from analytiq_data.flows.agent_loop.constants import (
    FLOW_AGENT_STREAM_ROUND_SECONDS,
    TOOL_RESULT_PREVIEW_CHARS,
)
from analytiq_data.flows.agent_loop.dispatch import execute_tool_call
from analytiq_data.flows.agent_loop.stream import emit_stream_event
from analytiq_data.flows.agent_loop.types import (
    FlowAgentConfig,
    FlowAgentResult,
    NormalizedToolCall,
    ToolCallRecord,
)
from analytiq_data.flows.tool_wiring import UnknownToolError, WiredToolRegistry

logger = logging.getLogger(__name__)


def _tool_call_to_dict(tc: Any) -> NormalizedToolCall:
    tid = getattr(tc, "id", None) or (tc.get("id", "") if isinstance(tc, dict) else "")
    fn = tc.function if hasattr(tc, "function") else tc.get("function", {})
    name = fn.name if hasattr(fn, "name") else fn.get("name", "")
    args_raw = fn.arguments if hasattr(fn, "arguments") else fn.get("arguments", "{}")
    if isinstance(args_raw, dict):
        args = args_raw
    else:
        try:
            args = json.loads(args_raw or "{}")
        except Exception:
            args = {}
    if not isinstance(args, dict):
        args = {}
    return NormalizedToolCall(id=str(tid or ""), name=str(name or ""), arguments=args)


def _preview(text: str) -> str:
    if len(text) <= TOOL_RESULT_PREVIEW_CHARS:
        return text
    return text[: TOOL_RESULT_PREVIEW_CHARS - 1] + "…"


def _assistant_message_dict(message: Any) -> dict[str, Any]:
    content = getattr(message, "content", None)
    tool_calls = getattr(message, "tool_calls", None)
    out: dict[str, Any] = {"role": "assistant", "content": content or ""}
    if tool_calls:
        serialized = []
        for tc in tool_calls:
            fn = tc.function if hasattr(tc, "function") else tc.get("function", {})
            serialized.append(
                {
                    "id": getattr(tc, "id", None) or tc.get("id", ""),
                    "type": "function",
                    "function": {
                        "name": fn.name if hasattr(fn, "name") else fn.get("name", ""),
                        "arguments": fn.arguments if hasattr(fn, "arguments") else fn.get("arguments", "{}"),
                    },
                }
            )
        out["tool_calls"] = serialized
    return out


class FlowAgentLoop:
    def __init__(
        self,
        *,
        analytiq_client: Any,
        organization_id: str,
        execution_context: "ad.flows.ExecutionContext",
        tool_registry: WiredToolRegistry,
        consumer_node_id: str,
        parent_item: "ad.flows.FlowItem",
        upstream_nodes_snapshot: dict[str, Any],
    ) -> None:
        self.analytiq_client = analytiq_client
        self.organization_id = organization_id
        self.ctx = execution_context
        self.registry = tool_registry
        self.consumer_node_id = consumer_node_id
        self.parent_item = parent_item
        self.upstream_nodes_snapshot = upstream_nodes_snapshot

    async def run(self, config: FlowAgentConfig) -> FlowAgentResult:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": config.system_message},
            {"role": "user", "content": config.user_message},
        ]
        tools = self.registry.openai_definitions()
        trace: list[ToolCallRecord] = []
        round_num = 0
        sink = self.ctx.stream_sink

        while round_num < config.max_tool_rounds:
            round_num += 1
            try:
                await billing.check_spu_limits(self.organization_id, config.model)
            except Exception as e:
                return FlowAgentResult(
                    text="",
                    tool_calls=trace,
                    rounds_used=round_num,
                    error=str(e),
                )

            await emit_stream_event(sink, {"type": "begin", "round": round_num})

            try:
                llm_provider = ad.llm.get_llm_model_provider(config.model)
                if llm_provider is None:
                    llm_provider = "openai"
                api_key = await ad.llm.get_llm_key(self.analytiq_client, llm_provider)
            except Exception as e:
                return FlowAgentResult(text="", tool_calls=trace, rounds_used=round_num, error=str(e))

            try:
                if config.enable_streaming and self.ctx.is_streaming and sink:
                    message = await self._stream_round(
                        config,
                        messages,
                        tools,
                        api_key,
                        round_num,
                    )
                else:
                    response = await asyncio.wait_for(
                        ad.llm.agent_completion(
                            self.analytiq_client,
                            config.model,
                            messages,
                            api_key,
                            tools=tools or None,
                            tool_choice="auto" if tools else None,
                        ),
                        timeout=FLOW_AGENT_STREAM_ROUND_SECONDS,
                    )
                    await billing.record_spu(response, self.organization_id, config.model)
                    message = response.choices[0].message
            except Exception as e:
                await emit_stream_event(sink, {"type": "error", "message": str(e)})
                return FlowAgentResult(text="", tool_calls=trace, rounds_used=round_num, error=str(e))

            tool_calls = getattr(message, "tool_calls", None) or []
            if not tool_calls:
                text = (getattr(message, "content", None) or "").strip()
                await emit_stream_event(
                    sink,
                    {
                        "type": "end",
                        "text": text,
                        "rounds_used": round_num,
                        "execution_id": self.ctx.execution_id,
                        "session_id": (self.parent_item.meta or {}).get("session_id"),
                    },
                )
                return FlowAgentResult(
                    text=text,
                    tool_calls=trace,
                    rounds_used=round_num,
                    max_rounds_reached=False,
                )

            messages.append(_assistant_message_dict(message))
            pending = [_tool_call_to_dict(tc) for tc in tool_calls]

            for tc in pending:
                if config.include_tool_trace:
                    await emit_stream_event(
                        sink,
                        {"type": "tool_call", "round": round_num, "tool": tc.name, "arguments": tc.arguments},
                    )
                started = time.time()
                try:
                    wired = self.registry.resolve(tc.name)
                    result_str = await execute_tool_call(
                        tc,
                        wired,
                        self.ctx,
                        consumer_node_id=self.consumer_node_id,
                        parent_item=self.parent_item,
                        upstream_nodes_snapshot=self.upstream_nodes_snapshot,
                    )
                    success = True
                    err_msg = None
                except UnknownToolError as e:
                    result_str = json.dumps({"error": str(e)})
                    success = False
                    err_msg = str(e)
                except Exception as e:
                    result_str = json.dumps({"error": str(e)})
                    success = False
                    err_msg = str(e)

                duration_ms = int((time.time() - started) * 1000)
                trace.append(
                    ToolCallRecord(
                        round=round_num,
                        tool=tc.name,
                        arguments=tc.arguments,
                        result_preview=_preview(result_str),
                        duration_ms=duration_ms,
                        success=success,
                        error=err_msg,
                    )
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result_str,
                    }
                )
                if config.include_tool_trace:
                    await emit_stream_event(
                        sink,
                        {
                            "type": "tool_result",
                            "round": round_num,
                            "tool": tc.name,
                            "preview": _preview(result_str),
                            "success": success,
                        },
                    )
                    logs = self.ctx.node_logs.setdefault(self.consumer_node_id, [])
                    logs.append(
                        f"agent_round={round_num} tool={tc.name} success={success} duration_ms={duration_ms}"
                    )

        await emit_stream_event(
            sink,
            {
                "type": "end",
                "text": "(Max tool rounds reached.)",
                "rounds_used": round_num,
                "execution_id": self.ctx.execution_id,
                "session_id": (self.parent_item.meta or {}).get("session_id"),
            },
        )
        return FlowAgentResult(
            text="(Max tool rounds reached.)",
            tool_calls=trace,
            rounds_used=round_num,
            max_rounds_reached=True,
        )

    async def _stream_round(
        self,
        config: FlowAgentConfig,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        api_key: str,
        round_num: int,
    ) -> Any:
        sink = self.ctx.stream_sink
        final_message = None

        async def _consume() -> Any:
            nonlocal final_message
            async for event_type, payload in ad.llm.agent_completion_stream(
                self.analytiq_client,
                config.model,
                messages,
                api_key,
                tools=tools or None,
                tool_choice="auto" if tools else None,
            ):
                if event_type == "content" and sink:
                    await emit_stream_event(sink, {"type": "content", "round": round_num, "chunk": payload})
                elif event_type == "thinking" and sink:
                    await emit_stream_event(sink, {"type": "thinking", "round": round_num, "chunk": payload})
                elif event_type == "message":
                    final_message = payload
                elif event_type == "usage":
                    await billing.record_spu_from_usage(payload, self.organization_id, config.model)
            return final_message

        result = await asyncio.wait_for(_consume(), timeout=FLOW_AGENT_STREAM_ROUND_SECONDS)
        if result is None:
            raise RuntimeError("Streaming LLM returned no final message")
        return result
