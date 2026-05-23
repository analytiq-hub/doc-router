"""Gmail API operations for ``flows.gmail`` (Phase 1: message send/get/getAll)."""

from __future__ import annotations

from typing import Any

import analytiq_data as ad

from .api import (
    gmail_api_request,
    gmail_api_request_all_items,
    resolve_oauth_access_token,
)
from .email_mime import encode_email_raw
from .helpers import (
    flatten_message_headers,
    prepare_emails_input,
    prepare_gmail_list_query,
    simplify_messages,
    validate_resource_operation,
)


async def _fetch_label_map(
    context: "ad.flows.ExecutionContext",
    token: str,
    node_id: str | None,
) -> dict[str, str]:
    data = await gmail_api_request(
        token,
        "GET",
        "/gmail/v1/users/me/labels",
        context=context,
        trace_node_id=node_id,
    )
    labels = data.get("labels") if isinstance(data, dict) else []
    out: dict[str, str] = {}
    if isinstance(labels, list):
        for row in labels:
            if isinstance(row, dict) and row.get("id") is not None:
                out[str(row["id"])] = str(row.get("name") or row["id"])
    return out


async def execute_gmail_item(
    context: "ad.flows.ExecutionContext",
    node: dict[str, Any],
    params: dict[str, Any],
    item: "ad.flows.FlowItem",
    *,
    item_index: int,
) -> "ad.flows.FlowItem":
    resource = str(params.get("resource") or "message")
    operation = str(params.get("operation") or "send")
    validate_resource_operation(resource, operation)
    token = await resolve_oauth_access_token(context, node)
    node_id = str(node.get("id") or "")

    if operation == "send":
        data = await _message_send(context, token, params, node_id=node_id)
    elif operation == "get":
        data = await _message_get(context, token, params, node_id=node_id)
    elif operation == "getAll":
        rows = await _message_get_all(context, token, params, node_id=node_id)
        return ad.flows.FlowItem(
            json={"messages": rows, "count": len(rows)},
            binary=dict(item.binary),
            meta=dict(item.meta),
        )
    else:
        raise ValueError(f"Unsupported operation: {operation}")

    return ad.flows.FlowItem(
        json=data if isinstance(data, dict) else {"data": data},
        binary=dict(item.binary),
        meta=dict(item.meta),
    )


async def _message_send(
    context: "ad.flows.ExecutionContext",
    token: str,
    params: dict[str, Any],
    *,
    node_id: str,
) -> dict[str, Any]:
    send_to = prepare_emails_input(str(params.get("sendTo") or ""), "To")
    subject = str(params.get("subject") or "")
    email_type = str(params.get("emailType") or "html")
    body = str(params.get("message") or "")

    options = params.get("options") if isinstance(params.get("options"), dict) else {}
    cc = prepare_emails_input(str(options.get("ccList") or ""), "CC") if options.get("ccList") else None
    bcc = prepare_emails_input(str(options.get("bccList") or ""), "BCC") if options.get("bccList") else None
    reply_to = (
        prepare_emails_input(str(options.get("replyTo") or ""), "Reply-To")
        if options.get("replyTo")
        else None
    )

    from_addr: str | None = None
    sender_name = str(options.get("senderName") or "").strip()
    if sender_name:
        profile = await gmail_api_request(
            token,
            "GET",
            "/gmail/v1/users/me/profile",
            context=context,
            trace_node_id=node_id,
        )
        email_address = str(profile.get("emailAddress") or "").strip() if isinstance(profile, dict) else ""
        if email_address:
            from_addr = f"{sender_name} <{email_address}>"

    body_text = body if email_type == "text" else None
    body_html = body if email_type == "html" else None
    raw = encode_email_raw(
        to=send_to,
        subject=subject,
        body_text=body_text,
        body_html=body_html,
        cc=cc or None,
        bcc=bcc or None,
        reply_to=reply_to,
        from_addr=from_addr,
    )
    return await gmail_api_request(
        token,
        "POST",
        "/gmail/v1/users/me/messages/send",
        body={"raw": raw},
        context=context,
        trace_node_id=node_id,
    )


async def _message_get(
    context: "ad.flows.ExecutionContext",
    token: str,
    params: dict[str, Any],
    *,
    node_id: str,
) -> dict[str, Any]:
    message_id = str(params.get("messageId") or "").strip()
    if not message_id:
        raise ValueError("messageId is required")

    simple = bool(params.get("simple", True))
    qs: dict[str, Any] = {}
    if simple:
        qs["format"] = "metadata"
        qs["metadataHeaders"] = ["From", "To", "Cc", "Bcc", "Subject"]
    else:
        qs["format"] = "full"

    msg = await gmail_api_request(
        token,
        "GET",
        f"/gmail/v1/users/me/messages/{message_id}",
        query=qs,
        context=context,
        trace_node_id=node_id,
    )
    if not isinstance(msg, dict):
        return {}
    if simple:
        label_map = await _fetch_label_map(context, token, node_id)
        simplified = await simplify_messages(token, [msg], label_map=label_map)
        return simplified[0] if simplified else flatten_message_headers(msg)
    return msg


async def _message_get_all(
    context: "ad.flows.ExecutionContext",
    token: str,
    params: dict[str, Any],
    *,
    node_id: str,
) -> list[dict[str, Any]]:
    return_all = bool(params.get("returnAll"))
    limit = int(params.get("limit") or 50)
    simple = bool(params.get("simple", True))
    filters = params.get("filters") if isinstance(params.get("filters"), dict) else {}

    qs = prepare_gmail_list_query(filters)
    if return_all:
        stubs = await gmail_api_request_all_items(
            context,
            token,
            "GET",
            "/gmail/v1/users/me/messages",
            "messages",
            query=qs,
            trace_node_id=node_id,
        )
    else:
        qs["maxResults"] = max(1, min(limit, 500))
        listed = await gmail_api_request(
            token,
            "GET",
            "/gmail/v1/users/me/messages",
            query=qs,
            context=context,
            trace_node_id=node_id,
        )
        stubs = listed.get("messages") if isinstance(listed, dict) else []
        if not isinstance(stubs, list):
            stubs = []

    fetch_qs: dict[str, Any] = {}
    if simple:
        fetch_qs["format"] = "metadata"
        fetch_qs["metadataHeaders"] = ["From", "To", "Cc", "Bcc", "Subject"]
    else:
        fetch_qs["format"] = "full"

    label_map = await _fetch_label_map(context, token, node_id) if simple else None
    results: list[dict[str, Any]] = []
    for stub in stubs:
        if not isinstance(stub, dict) or not stub.get("id"):
            continue
        mid = str(stub["id"])
        msg = await gmail_api_request(
            token,
            "GET",
            f"/gmail/v1/users/me/messages/{mid}",
            query=fetch_qs,
            context=context,
            trace_node_id=node_id,
        )
        if isinstance(msg, dict):
            results.append(msg)

    if simple and results:
        return await simplify_messages(token, results, label_map=label_map)
    return results
