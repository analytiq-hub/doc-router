"""Microsoft Graph Outlook operations for ``flows.microsoft_outlook``."""

from __future__ import annotations

import base64
from typing import Any

import analytiq_data as ad

from analytiq_data.flows.integrations.microsoft.graph_api import graph_encode_id

from .api import outlook_request, outlook_request_all_items, resolve_outlook_auth
from .attachments import (
    attachments_prefix,
    download_message_attachments,
    resolve_outlook_download_attachments,
)
from .helpers import (
    SIMPLE_MESSAGE_SELECT,
    additional_fields,
    create_message,
    format_message_output,
    list_query,
    message_resource_path,
    param_str,
    parse_recipients,
    validate_resource_operation,
)


async def execute_microsoft_outlook_item(
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
    token, _fields, mailbox_base = await resolve_outlook_auth(context, node)

    runners = {
        "message": _run_message,
        "folder": _run_folder,
        "draft": _run_draft,
        "folderMessage": _run_folder_message,
        "calendar": _run_calendar,
        "contact": _run_contact,
        "event": _run_event,
        "messageAttachment": _run_message_attachment,
    }
    data = await runners[resource](
        context,
        token,
        mailbox_base,
        operation,
        params,
        item,
        item_index=item_index,
    )

    if isinstance(data, ad.flows.FlowItem):
        return data
    return ad.flows.FlowItem(
        json=data if isinstance(data, dict) else {"data": data},
        binary=dict(item.binary),
        meta=dict(item.meta),
    )


async def _run_message(
    context: "ad.flows.ExecutionContext",
    token: str,
    mailbox_base: str,
    operation: str,
    params: dict[str, Any],
    item: "ad.flows.FlowItem",
    *,
    item_index: int,
) -> Any:
    if operation == "send":
        return await _message_send(context, token, mailbox_base, params, item, item_index)
    if operation == "get":
        return await _message_get(context, token, mailbox_base, params)
    if operation == "getAll":
        rows = await _message_get_all(context, token, mailbox_base, params)
        return {"messages": rows, "count": len(rows)}
    if operation == "delete":
        mid = param_str(params, "messageId")
        if not mid:
            raise ValueError("messageId is required")
        await outlook_request(context, token, mailbox_base, "DELETE", message_resource_path(mid))
        return {"success": True, "id": mid}
    if operation == "move":
        mid = param_str(params, "messageId")
        folder_id = param_str(params, "folderId")
        if not mid or not folder_id:
            raise ValueError("messageId and folderId are required")
        body = {"destinationId": folder_id}
        data = await outlook_request(
            context, token, mailbox_base, "POST", message_resource_path(mid, "/move"), body=body
        )
        return data if isinstance(data, dict) else {"data": data}
    if operation == "reply":
        mid = param_str(params, "messageId")
        if not mid:
            raise ValueError("messageId is required")
        comment = param_str(params, "comment", default=" ")
        body = {"comment": comment}
        await outlook_request(
            context, token, mailbox_base, "POST", message_resource_path(mid, "/reply"), body=body
        )
        return {"success": True}
    if operation == "update":
        mid = param_str(params, "messageId")
        if not mid:
            raise ValueError("messageId is required")
        fields = {**additional_fields(params)}
        fields.setdefault("subject", param_str(params, "subject"))
        fields.setdefault("bodyContent", param_str(params, "bodyContent"))
        message = create_message(fields)
        data = await outlook_request(
            context, token, mailbox_base, "PATCH", message_resource_path(mid), body=message
        )
        return data if isinstance(data, dict) else {"data": data}
    raise ValueError(f"Unsupported message operation: {operation}")


async def _message_send(
    context: "ad.flows.ExecutionContext",
    token: str,
    mailbox_base: str,
    params: dict[str, Any],
    item: "ad.flows.FlowItem",
    item_index: int,
) -> dict[str, Any]:
    fields = {**additional_fields(params)}
    fields["subject"] = param_str(params, "subject")
    fields["bodyContent"] = param_str(params, "bodyContent") or " "
    fields["toRecipients"] = param_str(params, "toRecipients")
    save_to_sent = fields.pop("saveToSentItems", True)
    if save_to_sent in ("false", "False", 0, "0"):
        save_to_sent = False

    message = create_message(fields)
    _attach_binary_to_message(message, params, item)

    body = {"message": message, "saveToSentItems": bool(save_to_sent)}
    await outlook_request(context, token, mailbox_base, "POST", "/sendMail", body=body)
    return {"success": True}


def _attach_binary_to_message(
    message: dict[str, Any], params: dict[str, Any], item: "ad.flows.FlowItem"
) -> None:
    extra = additional_fields(params)
    attachments = extra.get("attachments")
    if not isinstance(attachments, dict):
        return
    entries = attachments.get("attachments")
    if not isinstance(entries, list):
        return
    out: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        prop = str(entry.get("binaryPropertyName") or "").strip()
        if not prop or prop not in item.binary:
            raise ValueError(f'Binary property "{prop}" not found on input item')
        blob = item.binary[prop]
        raw = blob.data if blob.data is not None else b""
        data_b64 = base64.b64encode(raw).decode("ascii")
        out.append(
            {
                "@odata.type": "#microsoft.graph.fileAttachment",
                "name": blob.file_name or prop,
                "contentBytes": data_b64,
            }
        )
    if out:
        message["attachments"] = out


async def _message_get(
    context: "ad.flows.ExecutionContext",
    token: str,
    mailbox_base: str,
    params: dict[str, Any],
) -> dict[str, Any] | "ad.flows.FlowItem":
    mid = param_str(params, "messageId")
    if not mid:
        raise ValueError("messageId is required")
    output = param_str(params, "output", default="simple")
    qs: dict[str, Any] = {}
    if output == "fields":
        names = params.get("fields")
        if isinstance(names, list) and names:
            select_fields = [str(f) for f in names]
            if resolve_outlook_download_attachments(params) and "hasAttachments" not in select_fields:
                select_fields.append("hasAttachments")
            qs["$select"] = ",".join(select_fields)
    elif output == "simple":
        qs["$select"] = SIMPLE_MESSAGE_SELECT
    data = await outlook_request(
        context, token, mailbox_base, "GET", message_resource_path(mid), query=qs or None
    )
    if not isinstance(data, dict):
        return {"data": data}
    formatted = format_message_output(data, params)
    if not resolve_outlook_download_attachments(params):
        return formatted  # type: ignore[return-value]
    prefix = attachments_prefix(params)
    binary = await download_message_attachments(
        context, token, mailbox_base, data, prefix=prefix
    )
    json_out = formatted if isinstance(formatted, dict) else {"data": formatted}
    return ad.flows.FlowItem(json=json_out, binary=binary, meta={})


async def _message_get_all(
    context: "ad.flows.ExecutionContext",
    token: str,
    mailbox_base: str,
    params: dict[str, Any],
) -> list[dict[str, Any]]:
    qs = list_query(params)
    rows = await outlook_request_all_items(
        context, token, mailbox_base, "GET", "/messages", query=qs
    )
    formatted = format_message_output(rows, params)
    return formatted if isinstance(formatted, list) else [formatted]


async def _run_folder(
    context: "ad.flows.ExecutionContext",
    token: str,
    mailbox_base: str,
    operation: str,
    params: dict[str, Any],
    item: "ad.flows.FlowItem",
    *,
    item_index: int,
) -> Any:
    if operation == "create":
        name = param_str(params, "displayName")
        if not name:
            raise ValueError("displayName is required")
        opts = options_dict(params)
        parent = param_str(opts, "folderId")
        path = f"/mailFolders/{parent}/childFolders" if parent else "/mailFolders"
        return await outlook_request(
            context, token, mailbox_base, "POST", path, body={"displayName": name}
        )
    if operation == "get":
        fid = param_str(params, "folderId")
        if not fid:
            raise ValueError("folderId is required")
        return await outlook_request(
            context, token, mailbox_base, "GET", f"/mailFolders/{fid}"
        )
    if operation == "getAll":
        qs = list_query(params)
        opts = options_dict(params)
        parent = param_str(opts, "folderId")
        path = f"/mailFolders/{parent}/childFolders" if parent else "/mailFolders"
        rows = await outlook_request_all_items(
            context, token, mailbox_base, "GET", path, query=qs
        )
        return {"folders": rows, "count": len(rows)}
    if operation == "update":
        fid = param_str(params, "folderId")
        if not fid:
            raise ValueError("folderId is required")
        body: dict[str, Any] = {}
        if param_str(params, "displayName"):
            body["displayName"] = param_str(params, "displayName")
        return await outlook_request(
            context, token, mailbox_base, "PATCH", f"/mailFolders/{fid}", body=body
        )
    if operation == "delete":
        fid = param_str(params, "folderId")
        if not fid:
            raise ValueError("folderId is required")
        await outlook_request(context, token, mailbox_base, "DELETE", f"/mailFolders/{fid}")
        return {"success": True, "id": fid}
    raise ValueError(f"Unsupported folder operation: {operation}")


async def _run_draft(
    context: "ad.flows.ExecutionContext",
    token: str,
    mailbox_base: str,
    operation: str,
    params: dict[str, Any],
    item: "ad.flows.FlowItem",
    *,
    item_index: int,
) -> Any:
    if operation == "create":
        fields = {**additional_fields(params)}
        fields.setdefault("subject", param_str(params, "subject"))
        fields.setdefault("bodyContent", param_str(params, "bodyContent") or " ")
        fields.setdefault("toRecipients", param_str(params, "toRecipients"))
        message = create_message(fields)
        message["isDraft"] = True
        return await outlook_request(
            context, token, mailbox_base, "POST", "/messages", body=message
        )
    if operation == "get":
        did = param_str(params, "draftId") or param_str(params, "messageId")
        if not did:
            raise ValueError("draftId is required")
        data = await outlook_request(
            context, token, mailbox_base, "GET", message_resource_path(did)
        )
        return format_message_output(data, params) if isinstance(data, dict) else data
    if operation == "delete":
        did = param_str(params, "draftId") or param_str(params, "messageId")
        if not did:
            raise ValueError("draftId is required")
        await outlook_request(context, token, mailbox_base, "DELETE", message_resource_path(did))
        return {"success": True, "id": did}
    if operation == "send":
        did = param_str(params, "draftId") or param_str(params, "messageId")
        if not did:
            raise ValueError("draftId is required")
        await outlook_request(
            context, token, mailbox_base, "POST", message_resource_path(did, "/send")
        )
        return {"success": True}
    if operation == "update":
        did = param_str(params, "draftId") or param_str(params, "messageId")
        if not did:
            raise ValueError("draftId is required")
        fields = {**additional_fields(params)}
        message = create_message(fields)
        return await outlook_request(
            context, token, mailbox_base, "PATCH", message_resource_path(did), body=message
        )
    raise ValueError(f"Unsupported draft operation: {operation}")


async def _run_folder_message(
    context: "ad.flows.ExecutionContext",
    token: str,
    mailbox_base: str,
    operation: str,
    params: dict[str, Any],
    item: "ad.flows.FlowItem",
    *,
    item_index: int,
) -> Any:
    if operation != "getAll":
        raise ValueError(f"Unsupported folderMessage operation: {operation}")
    folder_id = param_str(params, "folderId")
    if not folder_id:
        raise ValueError("folderId is required")
    qs = list_query(params)
    rows = await outlook_request_all_items(
        context,
        token,
        mailbox_base,
        "GET",
        f"/mailFolders/{folder_id}/messages",
        query=qs,
    )
    formatted = format_message_output(rows, params)
    return {
        "messages": formatted if isinstance(formatted, list) else [formatted],
        "count": len(formatted) if isinstance(formatted, list) else 1,
    }


async def _run_calendar(
    context: "ad.flows.ExecutionContext",
    token: str,
    mailbox_base: str,
    operation: str,
    params: dict[str, Any],
    item: "ad.flows.FlowItem",
    *,
    item_index: int,
) -> Any:
    if operation == "create":
        name = param_str(params, "name")
        if not name:
            raise ValueError("name is required")
        return await outlook_request(
            context, token, mailbox_base, "POST", "/calendars", body={"name": name}
        )
    if operation == "get":
        cid = param_str(params, "calendarId")
        if not cid:
            raise ValueError("calendarId is required")
        return await outlook_request(
            context, token, mailbox_base, "GET", f"/calendars/{cid}"
        )
    if operation == "getAll":
        qs = list_query(params)
        rows = await outlook_request_all_items(
            context, token, mailbox_base, "GET", "/calendars", query=qs
        )
        return {"calendars": rows, "count": len(rows)}
    if operation == "update":
        cid = param_str(params, "calendarId")
        if not cid:
            raise ValueError("calendarId is required")
        body: dict[str, Any] = {}
        if param_str(params, "name"):
            body["name"] = param_str(params, "name")
        return await outlook_request(
            context, token, mailbox_base, "PATCH", f"/calendars/{cid}", body=body
        )
    if operation == "delete":
        cid = param_str(params, "calendarId")
        if not cid:
            raise ValueError("calendarId is required")
        await outlook_request(context, token, mailbox_base, "DELETE", f"/calendars/{cid}")
        return {"success": True, "id": cid}
    raise ValueError(f"Unsupported calendar operation: {operation}")


async def _run_contact(
    context: "ad.flows.ExecutionContext",
    token: str,
    mailbox_base: str,
    operation: str,
    params: dict[str, Any],
    item: "ad.flows.FlowItem",
    *,
    item_index: int,
) -> Any:
    if operation == "create":
        body: dict[str, Any] = {}
        for key in ("givenName", "surname", "displayName", "emailAddresses"):
            if param_str(params, key):
                body[key] = param_str(params, key)
        if not body:
            raise ValueError("At least one contact field is required")
        return await outlook_request(
            context, token, mailbox_base, "POST", "/contacts", body=body
        )
    if operation == "get":
        cid = param_str(params, "contactId")
        if not cid:
            raise ValueError("contactId is required")
        return await outlook_request(
            context, token, mailbox_base, "GET", f"/contacts/{cid}"
        )
    if operation == "getAll":
        qs = list_query(params)
        rows = await outlook_request_all_items(
            context, token, mailbox_base, "GET", "/contacts", query=qs
        )
        return {"contacts": rows, "count": len(rows)}
    if operation == "update":
        cid = param_str(params, "contactId")
        if not cid:
            raise ValueError("contactId is required")
        body = {k: param_str(params, k) for k in ("givenName", "surname", "displayName") if param_str(params, k)}
        return await outlook_request(
            context, token, mailbox_base, "PATCH", f"/contacts/{cid}", body=body
        )
    if operation == "delete":
        cid = param_str(params, "contactId")
        if not cid:
            raise ValueError("contactId is required")
        await outlook_request(context, token, mailbox_base, "DELETE", f"/contacts/{cid}")
        return {"success": True, "id": cid}
    raise ValueError(f"Unsupported contact operation: {operation}")


async def _run_event(
    context: "ad.flows.ExecutionContext",
    token: str,
    mailbox_base: str,
    operation: str,
    params: dict[str, Any],
    item: "ad.flows.FlowItem",
    *,
    item_index: int,
) -> Any:
    calendar_id = param_str(params, "calendarId")
    if operation == "create":
        if not calendar_id:
            raise ValueError("calendarId is required")
        body = {
            "subject": param_str(params, "subject"),
            "start": {
                "dateTime": param_str(params, "startDateTime"),
                "timeZone": param_str(params, "timeZone", default="UTC"),
            },
            "end": {
                "dateTime": param_str(params, "endDateTime"),
                "timeZone": param_str(params, "timeZone", default="UTC"),
            },
        }
        return await outlook_request(
            context,
            token,
            mailbox_base,
            "POST",
            f"/calendars/{calendar_id}/events",
            body=body,
        )
    if operation == "get":
        eid = param_str(params, "eventId")
        if not eid:
            raise ValueError("eventId is required")
        return await outlook_request(
            context, token, mailbox_base, "GET", f"/calendar/events/{eid}"
        )
    if operation == "getAll":
        if not calendar_id:
            raise ValueError("calendarId is required")
        qs = list_query(params)
        rows = await outlook_request_all_items(
            context,
            token,
            mailbox_base,
            "GET",
            f"/calendars/{calendar_id}/events",
            query=qs,
        )
        return {"events": rows, "count": len(rows)}
    if operation == "update":
        eid = param_str(params, "eventId")
        if not eid:
            raise ValueError("eventId is required")
        body: dict[str, Any] = {}
        if param_str(params, "subject"):
            body["subject"] = param_str(params, "subject")
        return await outlook_request(
            context, token, mailbox_base, "PATCH", f"/calendar/events/{eid}", body=body
        )
    if operation == "delete":
        eid = param_str(params, "eventId")
        if not eid:
            raise ValueError("eventId is required")
        await outlook_request(
            context, token, mailbox_base, "DELETE", f"/calendar/events/{eid}"
        )
        return {"success": True, "id": eid}
    raise ValueError(f"Unsupported event operation: {operation}")


async def _run_message_attachment(
    context: "ad.flows.ExecutionContext",
    token: str,
    mailbox_base: str,
    operation: str,
    params: dict[str, Any],
    item: "ad.flows.FlowItem",
    *,
    item_index: int,
) -> Any:
    mid = param_str(params, "messageId")
    if not mid:
        raise ValueError("messageId is required")
    if operation == "getAll":
        rows = await outlook_request_all_items(
            context,
            token,
            mailbox_base,
            "GET",
            message_resource_path(mid, "/attachments"),
        )
        return {"attachments": rows, "count": len(rows)}
    if operation == "get":
        aid = param_str(params, "attachmentId")
        if not aid:
            raise ValueError("attachmentId is required")
        return await outlook_request(
            context,
            token,
            mailbox_base,
            "GET",
            message_resource_path(mid, f"/attachments/{graph_encode_id(aid)}"),
        )
    if operation == "add":
        prop = param_str(params, "binaryPropertyName", default="data")
        if prop not in item.binary:
            raise ValueError(f'Binary property "{prop}" not found on input item')
        blob = item.binary[prop]
        raw = blob.data if blob.data is not None else b""
        body = {
            "@odata.type": "#microsoft.graph.fileAttachment",
            "name": param_str(params, "fileName") or blob.file_name or prop,
            "contentBytes": base64.b64encode(raw).decode("ascii"),
        }
        return await outlook_request(
            context,
            token,
            mailbox_base,
            "POST",
            message_resource_path(mid, "/attachments"),
            body=body,
        )
    if operation == "download":
        aid = param_str(params, "attachmentId")
        if not aid:
            raise ValueError("attachmentId is required")
        prop = param_str(params, "binaryPropertyName", default="data")
        data = await outlook_request(
            context,
            token,
            mailbox_base,
            "GET",
            message_resource_path(mid, f"/attachments/{graph_encode_id(aid)}/$value"),
            expect_json=False,
        )
        content = data if isinstance(data, bytes) else bytes(data)
        binary = {
            prop: ad.flows.BinaryRef(
                data=content,
                mime_type="application/octet-stream",
                file_name=param_str(params, "fileName") or prop,
            )
        }
        return ad.flows.FlowItem(json={"attachmentId": aid, "messageId": mid}, binary=binary, meta={})
    raise ValueError(f"Unsupported messageAttachment operation: {operation}")
