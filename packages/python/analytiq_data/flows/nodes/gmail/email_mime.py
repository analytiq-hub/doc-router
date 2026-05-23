"""RFC822 MIME helpers for Gmail ``messages.send`` (base64url ``raw``)."""

from __future__ import annotations

import base64
from email.message import EmailMessage

from .email_attachments import OutboundAttachment


def _split_mime_type(mime_type: str) -> tuple[str, str]:
    token = (mime_type or "application/octet-stream").split(";", 1)[0].strip().lower()
    if "/" in token:
        main, sub = token.split("/", 1)
        return main, sub
    return "application", "octet-stream"


def encode_email_raw(
    *,
    to: str,
    subject: str,
    body_text: str | None = None,
    body_html: str | None = None,
    cc: str | None = None,
    bcc: str | None = None,
    reply_to: str | None = None,
    from_addr: str | None = None,
    in_reply_to: str | None = None,
    references: str | None = None,
    attachments: list[OutboundAttachment] | None = None,
) -> str:
    """Build a MIME message and return Gmail-compatible base64url ``raw``."""

    msg = EmailMessage()
    if from_addr:
        msg["From"] = from_addr
    msg["To"] = to
    if cc:
        msg["Cc"] = cc
    if bcc:
        msg["Bcc"] = bcc
    if reply_to:
        msg["Reply-To"] = reply_to
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
    if references:
        msg["References"] = references
    msg["Subject"] = subject

    text = (body_text or "").strip()
    html = (body_html or "").strip()
    if html:
        msg.set_content(text or " ")
        msg.add_alternative(html, subtype="html")
    else:
        msg.set_content(text)

    for attachment in attachments or []:
        maintype, subtype = _split_mime_type(attachment.mime_type)
        msg.add_attachment(
            attachment.content,
            maintype=maintype,
            subtype=subtype,
            filename=attachment.name,
        )

    encoded = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")
    return encoded.rstrip("=")
