"""Parse Gmail ``format=raw`` messages into JSON + optional binary attachments."""

from __future__ import annotations

import base64
from email import policy
from email.message import Message
from email.parser import BytesParser
from typing import Any

import analytiq_data as ad


def decode_gmail_raw(raw_b64: str) -> bytes:
    """Decode Gmail base64url ``raw`` field."""

    token = (raw_b64 or "").strip()
    if not token:
        return b""
    padded = token + ("=" * (-len(token) % 4))
    std = padded.replace("-", "+").replace("_", "/")
    return base64.b64decode(std.encode("ascii"))


def _extract_body(msg: Message) -> tuple[str | None, str | None]:
    text: str | None = None
    html: str | None = None
    if msg.is_multipart():
        for part in msg.walk():
            if part.is_multipart() or _is_attachment_part(part):
                continue
            ctype = part.get_content_type()
            if ctype == "text/plain" and text is None:
                payload = part.get_payload(decode=True)
                if isinstance(payload, bytes):
                    text = payload.decode(part.get_content_charset() or "utf-8", errors="replace").strip()
            elif ctype == "text/html" and html is None:
                payload = part.get_payload(decode=True)
                if isinstance(payload, bytes):
                    html = payload.decode(part.get_content_charset() or "utf-8", errors="replace").strip()
    else:
        payload = msg.get_payload(decode=True)
        if isinstance(payload, bytes):
            decoded = payload.decode(msg.get_content_charset() or "utf-8", errors="replace").strip()
            if msg.get_content_type() == "text/html":
                html = decoded
            else:
                text = decoded
    return text, html


def _is_attachment_part(part: Message) -> bool:
    if part.is_multipart():
        return False
    ctype = (part.get_content_type() or "").lower()
    if ctype in ("text/plain", "text/html"):
        return False
    if ctype.startswith("multipart/"):
        return False
    if ctype in ("message/rfc822", "message/delivery-status"):
        return False
    disposition = (part.get_content_disposition() or "").lower()
    if disposition == "attachment":
        return True
    if part.get_filename():
        return True
    maintype = ctype.split("/", 1)[0]
    if maintype in ("application", "image", "audio", "video"):
        return True
    return False


def _collect_attachments(
    msg: Message,
    *,
    prefix: str,
    download: bool,
) -> dict[str, ad.flows.BinaryRef]:
    if not download:
        return {}
    binary: dict[str, ad.flows.BinaryRef] = {}
    idx = 0
    for part in msg.walk():
        if part.is_multipart():
            continue
        if not _is_attachment_part(part):
            continue
        payload = part.get_payload(decode=True)
        if not isinstance(payload, bytes) or not payload:
            continue
        name = part.get_filename() or f"attachment_{idx}"
        key = f"{prefix}{idx}"
        binary[key] = ad.flows.BinaryRef(
            mime_type=part.get_content_type() or "application/octet-stream",
            file_name=name,
            data=payload,
        )
        idx += 1
    return binary


def resolve_download_attachments(options: dict[str, Any], *, simple: bool) -> bool:
    """Return whether to download attachments; defaults to true when not simplifying."""

    if "downloadAttachments" in options:
        return bool(options.get("downloadAttachments"))
    return not simple


def parse_raw_email_bytes(
    data: bytes,
    *,
    gmail_meta: dict[str, Any] | None = None,
    download_attachments: bool = False,
    attachment_prefix: str = "attachment_",
) -> tuple[dict[str, Any], dict[str, ad.flows.BinaryRef]]:
    """Parse RFC822 bytes into a JSON-friendly dict and optional binaries."""

    msg = BytesParser(policy=policy.default).parsebytes(data)
    text, html = _extract_body(msg)
    headers: dict[str, str] = {}
    for key, val in msg.items():
        if key and val:
            headers[key] = val

    out: dict[str, Any] = dict(gmail_meta or {})
    out.update(
        {
            "subject": msg.get("Subject"),
            "from": msg.get("From"),
            "to": msg.get("To"),
            "cc": msg.get("Cc"),
            "bcc": msg.get("Bcc"),
            "replyTo": msg.get("Reply-To"),
            "messageId": msg.get("Message-ID"),
            "date": msg.get("Date"),
            "text": text,
            "html": html,
            "headers": headers,
        }
    )
    binary = _collect_attachments(
        msg,
        prefix=attachment_prefix,
        download=download_attachments,
    )
    return out, binary


def parse_gmail_api_message(
    gmail_msg: dict[str, Any],
    *,
    download_attachments: bool = False,
    attachment_prefix: str = "attachment_",
) -> tuple[dict[str, Any], dict[str, ad.flows.BinaryRef]]:
    """Parse a Gmail API message that includes a ``raw`` field."""

    raw = gmail_msg.get("raw")
    meta = {k: gmail_msg[k] for k in ("id", "threadId", "labelIds", "snippet", "sizeEstimate") if k in gmail_msg}
    if not isinstance(raw, str) or not raw.strip():
        return flatten_api_headers(gmail_msg), {}
    data = decode_gmail_raw(raw)
    parsed, binary = parse_raw_email_bytes(
        data,
        gmail_meta=meta,
        download_attachments=download_attachments,
        attachment_prefix=attachment_prefix,
    )
    return parsed, binary


def flatten_api_headers(gmail_msg: dict[str, Any]) -> dict[str, Any]:
    """Promote selected payload headers when ``raw`` is unavailable."""

    from .helpers import flatten_message_headers

    return flatten_message_headers(gmail_msg)
