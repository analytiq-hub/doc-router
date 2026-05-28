"""Gmail API operations for ``flows.gmail``."""

from __future__ import annotations

from typing import Any

import analytiq_data as ad

from .api import (
    gmail_api_request,
    gmail_api_request_all_items,
    resolve_oauth_access_token,
)
from .email_attachments import resolve_outbound_attachments
from .email_mime import encode_email_raw
from .email_parse import parse_gmail_api_message, resolve_download_attachments
from .helpers import (
    coerce_label_ids,
    flatten_message_headers,
    prepare_emails_input,
    prepare_gmail_list_query,
    prepare_message_body,
    simplify_messages,
    validate_resource_operation,
)
from .reply import reply_to_message


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


def _merge_flow_item(
    item: "ad.flows.FlowItem",
    result: "ad.flows.FlowItem | dict[str, Any]",
) -> "ad.flows.FlowItem":
    if isinstance(result, ad.flows.FlowItem):
        binary = dict(item.binary)
        binary.update(result.binary)
        return ad.flows.FlowItem(
            json=result.json,
            binary=binary,
            meta=dict(item.meta),
        )
    data = result if isinstance(result, dict) else {"data": result}
    return ad.flows.FlowItem(json=data, binary=dict(item.binary), meta=dict(item.meta))


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

    if resource == "message":
        result = await _run_message(context, token, params, operation, node_id=node_id, item=item)
    elif resource == "label":
        result = await _run_label(context, token, params, operation, node_id=node_id)
    elif resource == "draft":
        result = await _run_draft(context, token, params, operation, node_id=node_id, item=item)
    elif resource == "thread":
        result = await _run_thread(context, token, params, operation, node_id=node_id, item=item)
    else:
        raise ValueError(f"Unsupported resource: {resource}")

    return _merge_flow_item(item, result)


async def _run_message(
    context: "ad.flows.ExecutionContext",
    token: str,
    params: dict[str, Any],
    operation: str,
    *,
    node_id: str,
    item: "ad.flows.FlowItem",
) -> "ad.flows.FlowItem | dict[str, Any]":
    if operation == "send":
        return await _message_send(context, token, params, node_id=node_id, item=item)
    if operation == "get":
        return await _message_get(context, token, params, node_id=node_id)
    if operation == "getAll":
        rows = await _message_get_all(context, token, params, node_id=node_id)
        return ad.flows.FlowItem(
            json={"messages": rows, "count": len(rows)},
            binary={},
            meta={},
        )
    if operation == "reply":
        message_id = str(params.get("messageId") or "").strip()
        if not message_id:
            raise ValueError("messageId is required")
        return await reply_to_message(
            context, token, message_id=message_id, params=params, node_id=node_id, item=item
        )
    if operation == "delete":
        return await _message_delete(context, token, params, node_id=node_id)
    if operation == "markAsRead":
        return await _message_modify_labels(
            context, token, params, add=[], remove=["UNREAD"], node_id=node_id
        )
    if operation == "markAsUnread":
        return await _message_modify_labels(
            context, token, params, add=["UNREAD"], remove=[], node_id=node_id
        )
    if operation == "addLabels":
        label_ids = coerce_label_ids(params.get("labelIds"))
        if not label_ids:
            raise ValueError("labelIds is required")
        return await _message_modify_labels(
            context, token, params, add=label_ids, remove=[], node_id=node_id
        )
    if operation == "removeLabels":
        label_ids = coerce_label_ids(params.get("labelIds"))
        if not label_ids:
            raise ValueError("labelIds is required")
        return await _message_modify_labels(
            context, token, params, add=[], remove=label_ids, node_id=node_id
        )
    raise ValueError(f"Unsupported message operation: {operation}")


async def _run_label(
    context: "ad.flows.ExecutionContext",
    token: str,
    params: dict[str, Any],
    operation: str,
    *,
    node_id: str,
) -> "ad.flows.FlowItem | dict[str, Any]":
    if operation == "create":
        name = str(params.get("name") or "").strip()
        if not name:
            raise ValueError("name is required")
        body = {
            "name": name,
            "labelListVisibility": str(params.get("labelListVisibility") or "labelShow"),
            "messageListVisibility": str(params.get("messageListVisibility") or "show"),
        }
        return await gmail_api_request(
            token,
            "POST",
            "/gmail/v1/users/me/labels",
            body=body,
            context=context,
            trace_node_id=node_id,
        )
    if operation == "delete":
        label_id = str(params.get("labelId") or "").strip()
        if not label_id:
            raise ValueError("labelId is required")
        await gmail_api_request(
            token,
            "DELETE",
            f"/gmail/v1/users/me/labels/{label_id}",
            context=context,
            trace_node_id=node_id,
        )
        return {"success": True, "labelId": label_id}
    if operation == "get":
        label_id = str(params.get("labelId") or "").strip()
        if not label_id:
            raise ValueError("labelId is required")
        return await gmail_api_request(
            token,
            "GET",
            f"/gmail/v1/users/me/labels/{label_id}",
            context=context,
            trace_node_id=node_id,
        )
    if operation == "getAll":
        return_all = bool(params.get("returnAll"))
        limit = int(params.get("limit") or 50)
        if return_all:
            labels = await gmail_api_request_all_items(
                context,
                token,
                "GET",
                "/gmail/v1/users/me/labels",
                "labels",
                trace_node_id=node_id,
            )
        else:
            listed = await gmail_api_request(
                token,
                "GET",
                "/gmail/v1/users/me/labels",
                query={"maxResults": max(1, min(limit, 500))},
                context=context,
                trace_node_id=node_id,
            )
            labels = listed.get("labels") if isinstance(listed, dict) else []
            if not isinstance(labels, list):
                labels = []
        return ad.flows.FlowItem(
            json={"labels": labels, "count": len(labels)},
            binary={},
            meta={},
        )
    raise ValueError(f"Unsupported label operation: {operation}")


async def _run_draft(
    context: "ad.flows.ExecutionContext",
    token: str,
    params: dict[str, Any],
    operation: str,
    *,
    node_id: str,
    item: "ad.flows.FlowItem",
) -> "ad.flows.FlowItem | dict[str, Any]":
    if operation == "create":
        return await _draft_create(context, token, params, node_id=node_id, item=item)
    if operation == "get":
        return await _draft_get(context, token, params, node_id=node_id)
    if operation == "getAll":
        return_all = bool(params.get("returnAll"))
        limit = int(params.get("limit") or 50)
        qs: dict[str, Any] = {}
        if not return_all:
            qs["maxResults"] = max(1, min(limit, 500))
        if return_all:
            drafts = await gmail_api_request_all_items(
                context,
                token,
                "GET",
                "/gmail/v1/users/me/drafts",
                "drafts",
                query=qs or None,
                trace_node_id=node_id,
            )
        else:
            listed = await gmail_api_request(
                token,
                "GET",
                "/gmail/v1/users/me/drafts",
                query=qs,
                context=context,
                trace_node_id=node_id,
            )
            drafts = listed.get("drafts") if isinstance(listed, dict) else []
            if not isinstance(drafts, list):
                drafts = []
        simple = bool(params.get("simple", True))
        if simple and drafts:
            simplified: list[dict[str, Any]] = []
            for row in drafts:
                if isinstance(row, dict):
                    simplified.append(_simplify_draft_row(row))
            drafts = simplified
        return ad.flows.FlowItem(
            json={"drafts": drafts, "count": len(drafts)},
            binary={},
            meta={},
        )
    if operation == "delete":
        draft_id = str(params.get("draftId") or "").strip()
        if not draft_id:
            raise ValueError("draftId is required")
        await gmail_api_request(
            token,
            "DELETE",
            f"/gmail/v1/users/me/drafts/{draft_id}",
            context=context,
            trace_node_id=node_id,
        )
        return {"success": True, "draftId": draft_id}
    raise ValueError(f"Unsupported draft operation: {operation}")


async def _run_thread(
    context: "ad.flows.ExecutionContext",
    token: str,
    params: dict[str, Any],
    operation: str,
    *,
    node_id: str,
    item: "ad.flows.FlowItem",
) -> "ad.flows.FlowItem | dict[str, Any]":
    if operation == "get":
        return await _thread_get(context, token, params, node_id=node_id)
    if operation == "getAll":
        rows = await _thread_get_all(context, token, params, node_id=node_id)
        return ad.flows.FlowItem(
            json={"threads": rows, "count": len(rows)},
            binary={},
            meta={},
        )
    thread_id = str(params.get("threadId") or "").strip()
    if not thread_id and operation not in ("getAll",):
        raise ValueError("threadId is required")
    if operation == "delete":
        await gmail_api_request(
            token,
            "DELETE",
            f"/gmail/v1/users/me/threads/{thread_id}",
            context=context,
            trace_node_id=node_id,
        )
        return {"success": True, "threadId": thread_id}
    if operation == "trash":
        return await gmail_api_request(
            token,
            "POST",
            f"/gmail/v1/users/me/threads/{thread_id}/trash",
            context=context,
            trace_node_id=node_id,
        )
    if operation == "untrash":
        return await gmail_api_request(
            token,
            "POST",
            f"/gmail/v1/users/me/threads/{thread_id}/untrash",
            context=context,
            trace_node_id=node_id,
        )
    if operation == "addLabels":
        label_ids = coerce_label_ids(params.get("labelIds"))
        if not label_ids:
            raise ValueError("labelIds is required")
        return await _thread_modify_labels(
            context, token, thread_id, add=label_ids, remove=[], node_id=node_id
        )
    if operation == "removeLabels":
        label_ids = coerce_label_ids(params.get("labelIds"))
        if not label_ids:
            raise ValueError("labelIds is required")
        return await _thread_modify_labels(
            context, token, thread_id, add=[], remove=label_ids, node_id=node_id
        )
    if operation == "reply":
        message_id = str(params.get("messageId") or "").strip()
        if not message_id:
            raise ValueError("messageId is required")
        return await reply_to_message(
            context, token, message_id=message_id, params=params, node_id=node_id, item=item
        )
    raise ValueError(f"Unsupported thread operation: {operation}")


async def _message_send(
    context: "ad.flows.ExecutionContext",
    token: str,
    params: dict[str, Any],
    *,
    node_id: str,
    item: "ad.flows.FlowItem",
) -> dict[str, Any]:
    send_to = prepare_emails_input(str(params.get("sendTo") or ""), "To")
    subject = str(params.get("subject") or "")
    body_text, body_html = prepare_message_body(params)

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

    attachments = await resolve_outbound_attachments(context, item, options)
    raw = encode_email_raw(
        to=send_to,
        subject=subject,
        body_text=body_text,
        body_html=body_html,
        cc=cc or None,
        bcc=bcc or None,
        reply_to=reply_to,
        from_addr=from_addr,
        attachments=attachments or None,
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
) -> "ad.flows.FlowItem | dict[str, Any]":
    message_id = str(params.get("messageId") or "").strip()
    if not message_id:
        raise ValueError("messageId is required")

    simple = bool(params.get("simple", True))
    options = params.get("options") if isinstance(params.get("options"), dict) else {}
    qs: dict[str, Any] = {}
    if simple:
        qs["format"] = "metadata"
        qs["metadataHeaders"] = ["From", "To", "Cc", "Bcc", "Subject"]
    else:
        qs["format"] = "raw"

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

    if not simple:
        download = resolve_download_attachments(options, simple=simple)
        prefix = str(options.get("attachmentPrefix") or "attachment_")
        parsed, binary = parse_gmail_api_message(
            msg,
            download_attachments=download,
            attachment_prefix=prefix,
        )
        return ad.flows.FlowItem(json=parsed, binary=binary, meta={})

    label_map = await _fetch_label_map(context, token, node_id)
    simplified = await simplify_messages(token, [msg], label_map=label_map)
    return simplified[0] if simplified else flatten_message_headers(msg)


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
    options = params.get("options") if isinstance(params.get("options"), dict) else {}

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
        fetch_qs["format"] = "raw"

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
        if not isinstance(msg, dict):
            continue
        if simple:
            results.append(msg)
        else:
            download = resolve_download_attachments(options, simple=simple)
            prefix = str(options.get("attachmentPrefix") or "attachment_")
            parsed, _binary = parse_gmail_api_message(
                msg,
                download_attachments=download,
                attachment_prefix=prefix,
            )
            results.append(parsed)

    if simple and results:
        return await simplify_messages(token, results, label_map=label_map)
    return results


async def _message_delete(
    context: "ad.flows.ExecutionContext",
    token: str,
    params: dict[str, Any],
    *,
    node_id: str,
) -> dict[str, Any]:
    message_id = str(params.get("messageId") or "").strip()
    if not message_id:
        raise ValueError("messageId is required")
    await gmail_api_request(
        token,
        "DELETE",
        f"/gmail/v1/users/me/messages/{message_id}",
        context=context,
        trace_node_id=node_id,
    )
    return {"success": True, "messageId": message_id}


async def _message_modify_labels(
    context: "ad.flows.ExecutionContext",
    token: str,
    params: dict[str, Any],
    *,
    add: list[str],
    remove: list[str],
    node_id: str,
) -> dict[str, Any]:
    message_id = str(params.get("messageId") or "").strip()
    if not message_id:
        raise ValueError("messageId is required")
    body: dict[str, Any] = {}
    if add:
        body["addLabelIds"] = add
    if remove:
        body["removeLabelIds"] = remove
    return await gmail_api_request(
        token,
        "POST",
        f"/gmail/v1/users/me/messages/{message_id}/modify",
        body=body,
        context=context,
        trace_node_id=node_id,
    )


def _simplify_draft_row(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    message = out.get("message")
    if isinstance(message, dict):
        out["message"] = flatten_message_headers(message)
    return out


async def _draft_create(
    context: "ad.flows.ExecutionContext",
    token: str,
    params: dict[str, Any],
    *,
    node_id: str,
    item: "ad.flows.FlowItem",
) -> dict[str, Any]:
    send_to = prepare_emails_input(str(params.get("sendTo") or ""), "To")
    subject = str(params.get("subject") or "")
    body_text, body_html = prepare_message_body(params)
    options = params.get("options") if isinstance(params.get("options"), dict) else {}
    cc = prepare_emails_input(str(options.get("ccList") or ""), "CC") if options.get("ccList") else None
    bcc = prepare_emails_input(str(options.get("bccList") or ""), "BCC") if options.get("bccList") else None

    attachments = await resolve_outbound_attachments(context, item, options)
    raw = encode_email_raw(
        to=send_to,
        subject=subject,
        body_text=body_text,
        body_html=body_html,
        cc=cc,
        bcc=bcc,
        attachments=attachments or None,
    )
    message_body: dict[str, Any] = {"raw": raw}
    thread_id = str(params.get("threadId") or "").strip()
    if thread_id:
        message_body["threadId"] = thread_id
    return await gmail_api_request(
        token,
        "POST",
        "/gmail/v1/users/me/drafts",
        body={"message": message_body},
        context=context,
        trace_node_id=node_id,
    )


async def _draft_get(
    context: "ad.flows.ExecutionContext",
    token: str,
    params: dict[str, Any],
    *,
    node_id: str,
) -> "ad.flows.FlowItem | dict[str, Any]":
    draft_id = str(params.get("draftId") or "").strip()
    if not draft_id:
        raise ValueError("draftId is required")
    simple = bool(params.get("simple", True))
    options = params.get("options") if isinstance(params.get("options"), dict) else {}

    draft = await gmail_api_request(
        token,
        "GET",
        f"/gmail/v1/users/me/drafts/{draft_id}",
        context=context,
        trace_node_id=node_id,
    )
    if not isinstance(draft, dict):
        return {}
    message = draft.get("message")
    if not isinstance(message, dict):
        return draft

    if simple:
        out = dict(draft)
        out["message"] = flatten_message_headers(message)
        return out

    msg = await gmail_api_request(
        token,
        "GET",
        f"/gmail/v1/users/me/messages/{message.get('id')}",
        query={"format": "raw"},
        context=context,
        trace_node_id=node_id,
    )
    if not isinstance(msg, dict):
        return draft
    download = resolve_download_attachments(options, simple=simple)
    prefix = str(options.get("attachmentPrefix") or "attachment_")
    parsed, binary = parse_gmail_api_message(
        msg,
        download_attachments=download,
        attachment_prefix=prefix,
    )
    out = dict(draft)
    out["message"] = parsed
    return ad.flows.FlowItem(json=out, binary=binary, meta={})


async def _thread_get(
    context: "ad.flows.ExecutionContext",
    token: str,
    params: dict[str, Any],
    *,
    node_id: str,
) -> "ad.flows.FlowItem | dict[str, Any]":
    thread_id = str(params.get("threadId") or "").strip()
    if not thread_id:
        raise ValueError("threadId is required")
    simple = bool(params.get("simple", True))
    options = params.get("options") if isinstance(params.get("options"), dict) else {}
    only_messages = bool(options.get("onlyMessages"))

    qs: dict[str, Any] = {"format": "metadata" if simple else "full"}
    thread = await gmail_api_request(
        token,
        "GET",
        f"/gmail/v1/users/me/threads/{thread_id}",
        query=qs,
        context=context,
        trace_node_id=node_id,
    )
    if not isinstance(thread, dict):
        return {}

    messages = thread.get("messages")
    if not isinstance(messages, list):
        messages = []

    if simple:
        label_map = await _fetch_label_map(context, token, node_id)
        simplified = await simplify_messages(token, messages, label_map=label_map)
        if only_messages:
            return {"messages": simplified, "count": len(simplified)}
        out = dict(thread)
        out["messages"] = simplified
        return out

    if only_messages:
        return {"messages": messages, "count": len(messages)}
    return thread


async def _thread_get_all(
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
            "/gmail/v1/users/me/threads",
            "threads",
            query=qs,
            trace_node_id=node_id,
        )
    else:
        qs["maxResults"] = max(1, min(limit, 500))
        listed = await gmail_api_request(
            token,
            "GET",
            "/gmail/v1/users/me/threads",
            query=qs,
            context=context,
            trace_node_id=node_id,
        )
        stubs = listed.get("threads") if isinstance(listed, dict) else []
        if not isinstance(stubs, list):
            stubs = []

    if not simple:
        return [row for row in stubs if isinstance(row, dict)]

    label_map = await _fetch_label_map(context, token, node_id)
    results: list[dict[str, Any]] = []
    for stub in stubs:
        if not isinstance(stub, dict) or not stub.get("id"):
            continue
        tid = str(stub["id"])
        thread = await gmail_api_request(
            token,
            "GET",
            f"/gmail/v1/users/me/threads/{tid}",
            query={"format": "metadata"},
            context=context,
            trace_node_id=node_id,
        )
        if not isinstance(thread, dict):
            continue
        messages = thread.get("messages")
        if isinstance(messages, list):
            thread = dict(thread)
            thread["messages"] = await simplify_messages(token, messages, label_map=label_map)
        results.append(thread)
    return results


async def _thread_modify_labels(
    context: "ad.flows.ExecutionContext",
    token: str,
    thread_id: str,
    *,
    add: list[str],
    remove: list[str],
    node_id: str,
) -> dict[str, Any]:
    body: dict[str, Any] = {}
    if add:
        body["addLabelIds"] = add
    if remove:
        body["removeLabelIds"] = remove
    return await gmail_api_request(
        token,
        "POST",
        f"/gmail/v1/users/me/threads/{thread_id}/modify",
        body=body,
        context=context,
        trace_node_id=node_id,
    )
