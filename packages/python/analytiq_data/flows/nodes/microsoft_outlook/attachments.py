"""Download Outlook message attachments into ``FlowItem.binary``."""

from __future__ import annotations

import base64
from typing import Any

import analytiq_data as ad

from analytiq_data.flows.integrations.microsoft.graph_api import graph_encode_id

from .api import outlook_request, outlook_request_all_items
from .helpers import message_resource_path


def resolve_outlook_download_attachments(params: dict[str, Any]) -> bool:
    """Simple: never. Raw: always. Fields: when ``downloadAttachments`` is true."""

    output = str(params.get("output") or "simple").strip().lower()
    if output == "simple":
        return False
    if output == "raw":
        return True
    options = params.get("options") if isinstance(params.get("options"), dict) else {}
    return bool(params.get("downloadAttachments") or options.get("downloadAttachments"))


def attachments_prefix(params: dict[str, Any]) -> str:
    options = params.get("options") if isinstance(params.get("options"), dict) else {}
    return str(
        params.get("attachmentsPrefix")
        or options.get("attachmentsPrefix")
        or "attachment_"
    )


async def download_message_attachments(
    context: "ad.flows.ExecutionContext",
    token: str,
    mailbox_base: str,
    message: dict[str, Any],
    *,
    prefix: str = "attachment_",
) -> dict[str, ad.flows.BinaryRef]:
    if message.get("hasAttachments") is False:
        return {}
    mid = str(message.get("id") or "").strip()
    if not mid:
        return {}

    rows = await outlook_request_all_items(
        context,
        token,
        mailbox_base,
        "GET",
        message_resource_path(mid, "/attachments"),
    )
    binary: dict[str, ad.flows.BinaryRef] = {}
    for index, att in enumerate(rows):
        if not isinstance(att, dict):
            continue
        aid = str(att.get("id") or "").strip()
        if not aid:
            continue
        name = str(att.get("name") or f"{prefix}{index}")
        content_type = str(att.get("contentType") or "application/octet-stream")

        content_b64 = att.get("contentBytes")
        if isinstance(content_b64, str) and content_b64:
            raw = base64.b64decode(content_b64)
        else:
            payload = await outlook_request(
                context,
                token,
                mailbox_base,
                "GET",
                message_resource_path(mid, f"/attachments/{graph_encode_id(aid)}/$value"),
                expect_json=False,
            )
            raw = payload if isinstance(payload, bytes) else bytes(payload)

        binary[f"{prefix}{index}"] = ad.flows.BinaryRef(
            mime_type=content_type,
            file_name=name,
            data=raw,
            file_size=len(raw),
        )
    return binary
