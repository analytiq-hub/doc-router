"""Microsoft Outlook trigger poll logic (n8n ``MicrosoftOutlookTrigger`` parity)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import analytiq_data as ad

from .api import outlook_request, outlook_request_all_items, resolve_outlook_auth_for_org
from .attachments import (
    attachments_prefix,
    download_message_attachments,
    resolve_outlook_download_attachments,
)
from .helpers import SIMPLE_MESSAGE_SELECT, prepare_trigger_filters, simplify_messages

LAST_TIME_CHECKED_KEY = "last_time_checked"


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _build_poll_query(
    params: dict[str, Any],
    *,
    poll_start: str,
    poll_end: str,
    manual: bool,
) -> dict[str, Any]:
    qs: dict[str, Any] = {}
    output = str(params.get("output") or "simple")
    if output == "fields":
        fields = params.get("fields")
        if isinstance(fields, list) and fields:
            select_fields = list(fields)
            if resolve_outlook_download_attachments(params) and "hasAttachments" not in select_fields:
                select_fields.append("hasAttachments")
            qs["$select"] = ",".join(str(f) for f in select_fields)
    elif output == "simple":
        qs["$select"] = SIMPLE_MESSAGE_SELECT

    filters = params.get("filters") if isinstance(params.get("filters"), dict) else {}
    filter_parts: list[str] = []
    user_filter = prepare_trigger_filters(filters)
    if user_filter:
        filter_parts.append(user_filter)
    if not manual:
        filter_parts.append(f"receivedDateTime ge {poll_start}")
        filter_parts.append(f"receivedDateTime lt {poll_end}")
    if filter_parts:
        qs["$filter"] = " and ".join(filter_parts)
    if manual:
        qs["$top"] = 1
        qs["$orderby"] = "receivedDateTime desc"
    return qs


def _rows_from_poll_response(
    page: Any,
    *,
    output: str,
) -> list[dict[str, Any]]:
    if isinstance(page, list):
        rows = [r for r in page if isinstance(r, dict)]
    elif isinstance(page, dict):
        chunk = page.get("value")
        rows = [r for r in chunk if isinstance(r, dict)] if isinstance(chunk, list) else []
    else:
        rows = []
    if output == "simple":
        return simplify_messages(rows)
    return rows


async def poll_microsoft_outlook_trigger(
    context: "ad.flows.PollContext",
    node: dict[str, Any],
    *,
    execution: "ad.flows.ExecutionContext | None" = None,
) -> list[list[ad.flows.FlowItem]] | None:
    params = node.get("parameters") if isinstance(node.get("parameters"), dict) else {}
    manual = context.mode == "manual"
    testing = bool(context.tick_meta.get("testing"))
    output = str(params.get("output") or "simple")

    token, _fields, mailbox_base = await resolve_outlook_auth_for_org(
        context.organization_id, node
    )
    trace_id = context.node_id

    now_iso = _utc_now_iso()

    if testing:
        from analytiq_data.flows.integrations.microsoft import graph_request

        await graph_request(
            token,
            "GET",
            "/messages",
            mailbox_base=mailbox_base,
            query={"$top": 1},
        )
        context.set_static(LAST_TIME_CHECKED_KEY, now_iso)
        return None

    start_iso = str(context.get_static(LAST_TIME_CHECKED_KEY) or now_iso)
    end_iso = now_iso

    if not manual and context.get_static(LAST_TIME_CHECKED_KEY) is None:
        context.set_static(LAST_TIME_CHECKED_KEY, end_iso)
        return None

    qs = _build_poll_query(
        params, poll_start=start_iso, poll_end=end_iso, manual=manual
    )

    if execution is not None:
        exec_ctx = execution
        exec_ctx.active_trace_node_id = trace_id
    else:
        exec_ctx = ad.flows.ExecutionContext(
            execution_id="poll",
            flow_id=context.flow_id,
            flow_revid=context.flow_revid,
            organization_id=context.organization_id,
            mode=context.mode,  # type: ignore[arg-type]
            trigger_data={},
            run_data={},
            revision_nodes=[],
            credentials={},
            analytiq_client=None,
        )
        exec_ctx.active_trace_node_id = trace_id

    try:
        if manual:
            page = await outlook_request(
                exec_ctx, token, mailbox_base, "GET", "/messages", query=qs
            )
            rows = _rows_from_poll_response(page, output=output)
        else:
            rows = await outlook_request_all_items(
                exec_ctx, token, mailbox_base, "GET", "/messages", query=qs
            )
            if output == "simple":
                rows = simplify_messages(rows)
    except Exception:
        if manual or context.get_static(LAST_TIME_CHECKED_KEY) is None:
            raise
        return None

    context.set_static(LAST_TIME_CHECKED_KEY, end_iso)

    if not rows:
        return None

    download = resolve_outlook_download_attachments(params)
    prefix = attachments_prefix(params)

    items: list[ad.flows.FlowItem] = []
    for i, row in enumerate(rows):
        binary: dict[str, ad.flows.BinaryRef] = {}
        if download:
            binary = await download_message_attachments(
                exec_ctx, token, mailbox_base, row, prefix=prefix
            )
        items.append(
            ad.flows.FlowItem(
                json=row,
                binary=binary,
                meta={"source_node_id": trace_id, "item_index": i},
                paired_item=i,
            )
        )
    return [items]
