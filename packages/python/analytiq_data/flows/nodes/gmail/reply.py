"""Reply-to-message helper (n8n ``replyToEmail``)."""

from __future__ import annotations

from typing import Any

import analytiq_data as ad

from .api import gmail_api_request
from .email_attachments import resolve_outbound_attachments
from .email_mime import encode_email_raw
from .helpers import header_from_payload, prepare_emails_input, prepare_message_body


async def reply_to_message(
    context: Any,
    token: str,
    *,
    message_id: str,
    params: dict[str, Any],
    node_id: str,
    item: "ad.flows.FlowItem",
) -> dict[str, Any]:
    options = params.get("options") if isinstance(params.get("options"), dict) else {}
    if options.get("replyToSenderOnly") and options.get("replyToRecipientsOnly"):
        raise ValueError(
            'Both "replyToSenderOnly" and "replyToRecipientsOnly" cannot be enabled at the same time.'
        )

    meta = await gmail_api_request(
        token,
        "GET",
        f"/gmail/v1/users/me/messages/{message_id}",
        query={"format": "metadata", "metadataHeaders": ["From", "To", "Cc", "Reply-To", "Subject", "Message-ID"]},
        context=context,
        trace_node_id=node_id,
    )
    if not isinstance(meta, dict):
        raise ValueError("Failed to load message metadata for reply")

    payload = meta.get("payload") if isinstance(meta.get("payload"), dict) else {}
    thread_id = meta.get("threadId")

    subject = header_from_payload(payload, "Subject") or ""
    if subject and not subject.lower().startswith("re:"):
        subject = f"Re: {subject}"

    message_id_header = header_from_payload(payload, "Message-ID") or ""

    profile = await gmail_api_request(
        token,
        "GET",
        "/gmail/v1/users/me/profile",
        context=context,
        trace_node_id=node_id,
    )
    own_email = str(profile.get("emailAddress") or "").strip() if isinstance(profile, dict) else ""

    reply_to_sender_only = bool(options.get("replyToSenderOnly"))
    reply_to_recipients_only = bool(options.get("replyToRecipientsOnly"))

    reply_header = "Reply-To" if header_from_payload(payload, "Reply-To") else "From"
    to_addrs: list[str] = []

    def _maybe_add(addr: str) -> None:
        a = (addr or "").strip()
        if not a or own_email and own_email in a:
            return
        if "<" in a and ">" in a:
            to_addrs.append(a)
        else:
            to_addrs.append(f"<{a}>")

    if not reply_to_recipients_only:
        _maybe_add(header_from_payload(payload, reply_header))

    if not reply_to_sender_only:
        to_header = header_from_payload(payload, "To") or ""
        for part in to_header.split(","):
            _maybe_add(part)

    # Dedupe while preserving order
    seen: set[str] = set()
    unique_to: list[str] = []
    for addr in to_addrs:
        if addr not in seen:
            seen.add(addr)
            unique_to.append(addr)
    to_string = ", ".join(unique_to)

    cc = prepare_emails_input(str(options.get("ccList") or ""), "CC") if options.get("ccList") else None
    bcc = prepare_emails_input(str(options.get("bccList") or ""), "BCC") if options.get("bccList") else None

    from_addr: str | None = None
    sender_name = str(options.get("senderName") or "").strip()
    if sender_name and own_email:
        from_addr = f"{sender_name} <{own_email}>"

    body_text, body_html = prepare_message_body(params)
    attachments = await resolve_outbound_attachments(context, item, options)
    raw = encode_email_raw(
        to=to_string,
        subject=subject,
        body_text=body_text,
        body_html=body_html,
        cc=cc,
        bcc=bcc,
        from_addr=from_addr,
        in_reply_to=message_id_header or None,
        references=message_id_header or None,
        attachments=attachments or None,
    )
    body: dict[str, Any] = {"raw": raw}
    if thread_id:
        body["threadId"] = thread_id
    return await gmail_api_request(
        token,
        "POST",
        "/gmail/v1/users/me/messages/send",
        body=body,
        context=context,
        trace_node_id=node_id,
    )
