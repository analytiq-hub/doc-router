"""Nested sub-flow execution (n8n-style: entry trigger + last-node return)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, NamedTuple

from bson import ObjectId

import analytiq_data as ad
from analytiq_data.flows.agent_loop.constants import FLOW_SUBFLOW_MAX_DEPTH, FLOW_SUBFLOW_TIMEOUT_SECONDS
from analytiq_data.flows.engine import extract_last_node_output_json, pick_webhook_last_node_id

logger = logging.getLogger(__name__)

SUBFLOW_ENTRY_TRIGGER = "flows.trigger.tool"


class SubFlowError(Exception):
    """User-facing sub-flow failure (mapped to JSON error or node error)."""


class SubFlowRunResult(NamedTuple):
    context: "ad.flows.ExecutionContext"
    revision: dict[str, Any]
    entry_trigger_id: str


async def load_active_subflow_revision(
    db: Any,
    *,
    organization_id: str,
    target_flow_id: str,
    require_callable_as_tool: bool = False,
) -> tuple[dict[str, Any], dict[str, Any], str]:
    """Return (flow_doc, revision_dict, rev_id)."""

    try:
        flow_oid = ObjectId(target_flow_id)
    except Exception as e:
        raise SubFlowError("Invalid target flow id") from e

    flow_doc = await db.flows.find_one({"_id": flow_oid, "organization_id": organization_id})
    if not flow_doc:
        raise SubFlowError("Target flow not found")
    if require_callable_as_tool and not flow_doc.get("callable_as_tool"):
        raise SubFlowError("Target flow is not callable as a tool")
    if not flow_doc.get("active") or not flow_doc.get("active_flow_revid"):
        raise SubFlowError("Target flow is not active")

    rev_id = str(flow_doc["active_flow_revid"])
    try:
        revision_doc = await db.flow_revisions.find_one({"_id": ObjectId(rev_id), "flow_id": target_flow_id})
    except Exception:
        revision_doc = None
    if not revision_doc:
        raise SubFlowError("Target flow revision not found")

    revision = {
        "nodes": revision_doc.get("nodes") or [],
        "connections": revision_doc.get("connections") or {},
        "settings": revision_doc.get("settings") or {},
        "pin_data": revision_doc.get("pin_data"),
    }
    return flow_doc, revision, rev_id


def find_subflow_entry_trigger_id(revision: dict[str, Any]) -> str:
    entry_id: str | None = None
    for n in revision.get("nodes") or []:
        if isinstance(n, dict) and n.get("type") == SUBFLOW_ENTRY_TRIGGER:
            if entry_id is not None:
                raise SubFlowError("Sub-flow must have exactly one Sub-flow entry trigger")
            entry_id = str(n.get("id") or "")
    if not entry_id:
        raise SubFlowError("Sub-flow is missing Sub-flow entry trigger")
    return entry_id


async def run_nested_subflow(
    *,
    parent_ctx: "ad.flows.ExecutionContext",
    target_flow_id: str,
    trigger_data: dict[str, Any],
    require_callable_as_tool: bool = False,
    mode: str = "sub_flow",
    timeout: float = FLOW_SUBFLOW_TIMEOUT_SECONDS,
) -> SubFlowRunResult:
    """Run target flow's active revision; return value read via ``resolve_subflow_return_*``."""

    stack = list(parent_ctx.flow_id_stack or [])
    if target_flow_id in stack:
        raise SubFlowError("Sub-flow cycle detected")
    if len(stack) >= FLOW_SUBFLOW_MAX_DEPTH:
        raise SubFlowError("Sub-flow depth limit exceeded")

    client = parent_ctx.analytiq_client
    if client is None or not hasattr(client, "mongodb_async"):
        raise SubFlowError("Sub-flow execution requires database client")

    db = ad.common.get_async_db(client)
    _flow_doc, revision, rev_id = await load_active_subflow_revision(
        db,
        organization_id=parent_ctx.organization_id,
        target_flow_id=target_flow_id,
        require_callable_as_tool=require_callable_as_tool,
    )
    entry_trigger_id = find_subflow_entry_trigger_id(revision)

    sub_exec_id = str(ObjectId())
    sub_ctx = ad.flows.ExecutionContext(
        organization_id=parent_ctx.organization_id,
        execution_id=sub_exec_id,
        flow_id=target_flow_id,
        flow_revid=rev_id,
        mode=mode,  # type: ignore[arg-type]
        trigger_data=dict(trigger_data),
        run_data={},
        analytiq_client=client,
        flow_id_stack=stack + [parent_ctx.flow_id],
    )
    try:
        await asyncio.wait_for(
            ad.flows.run_flow(
                context=sub_ctx,
                revision=revision,
                start_trigger_node_id=entry_trigger_id,
            ),
            timeout=timeout,
        )
    except asyncio.TimeoutError as e:
        raise SubFlowError("Sub-flow execution timed out") from e
    except SubFlowError:
        raise
    except Exception as e:
        raise SubFlowError(str(e)) from e

    return SubFlowRunResult(context=sub_ctx, revision=revision, entry_trigger_id=entry_trigger_id)


def resolve_subflow_return_json(
    run: SubFlowRunResult,
) -> Any:
    """Tool / scalar return from the last executed node (webhook heuristic)."""

    sub_ctx = run.context
    value = extract_last_node_output_json(
        sub_ctx.run_data,
        run.revision,
        start_trigger_node_id=run.entry_trigger_id,
    )
    if value is None:
        raise SubFlowError("Sub-flow did not produce output")
    return value


def resolve_subflow_return_items(
    run: SubFlowRunResult,
) -> list["ad.flows.FlowItem"]:
    """Main-path return: items from last executed node's primary output branch."""

    sub_ctx = run.context
    last_node_id = pick_webhook_last_node_id(
        sub_ctx.run_data,
        run.revision,
        start_trigger_node_id=run.entry_trigger_id,
    )
    if not isinstance(last_node_id, str):
        raise SubFlowError("Sub-flow did not produce output")

    ent = sub_ctx.run_data.get(last_node_id) or {}
    main = ent.get("data", {}).get("main") if isinstance(ent, dict) else None
    if not isinstance(main, list) or not main or not isinstance(main[0], list) or not main[0]:
        raise SubFlowError("Sub-flow did not produce output")

    out: list[ad.flows.FlowItem] = []
    for raw in main[0]:
        if isinstance(raw, ad.flows.FlowItem):
            out.append(raw)
        elif isinstance(raw, dict):
            out.append(
                ad.flows.FlowItem(
                    json=raw.get("json", raw),
                    binary=raw.get("binary") or {},
                    meta=raw.get("meta") or {},
                    paired_item=raw.get("paired_item"),
                )
            )
    if not out:
        raise SubFlowError("Sub-flow did not produce output")
    return out
