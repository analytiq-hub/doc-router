"""RFC822 MIME helpers for Gmail ``messages.send`` (base64url ``raw``)."""

from __future__ import annotations

import base64
from email.message import EmailMessage


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
    msg["Subject"] = subject

    text = (body_text or "").strip()
    html = (body_html or "").strip()
    if html:
        msg.set_content(text or " ")
        msg.add_alternative(html, subtype="html")
    else:
        msg.set_content(text)

    encoded = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")
    return encoded.rstrip("=")
