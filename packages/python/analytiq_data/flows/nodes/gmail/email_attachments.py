"""Resolve outbound email attachments from ``FlowItem.binary``."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import analytiq_data as ad


@dataclass(frozen=True)
class OutboundAttachment:
    name: str
    content: bytes
    mime_type: str


def _parse_attachment_entries(entries: Any) -> list[str]:
    names: list[str] = []

    def _add_property(raw: Any) -> None:
        if not isinstance(raw, str) or not raw.strip():
            return
        for part in raw.split(","):
            p = part.strip()
            if p:
                names.append(p)

    if not isinstance(entries, list):
        return names
    for entry in entries:
        if isinstance(entry, str):
            _add_property(entry)
        elif isinstance(entry, dict):
            _add_property(entry.get("property"))
    return names


def attachment_binary_property_names(
    options: dict[str, Any],
    item: "ad.flows.FlowItem | None" = None,
) -> list[str]:
    """
    Parse attachment binary property names from node ``options``.

    Supports n8n shape ``attachmentsUi.attachmentsBinary: [{property: \"data\"}]``
    and DocRouter shorthand ``attachmentsBinary: [\"data\", \"report\"]``.

    When ``attachmentsBinary`` is omitted, defaults to **all keys** on ``item.binary``
    so send/reply can attach pinned or upstream binaries without extra JSON config.
    Set ``attachmentsBinary: []`` to send with no attachments.
    """

    if "attachmentsBinary" in options:
        return _parse_attachment_entries(options.get("attachmentsBinary"))
    ui = options.get("attachmentsUi")
    if isinstance(ui, dict) and "attachmentsBinary" in ui:
        return _parse_attachment_entries(ui.get("attachmentsBinary"))
    if item and item.binary:
        return list(item.binary.keys())
    return []


async def resolve_outbound_attachments(
    context: "ad.flows.ExecutionContext",
    item: "ad.flows.FlowItem",
    options: dict[str, Any],
) -> list[OutboundAttachment]:
    property_names = attachment_binary_property_names(options, item)
    if not property_names:
        return []

    out: list[OutboundAttachment] = []
    for prop in property_names:
        raw = item.binary.get(prop)
        if raw is None:
            raise ValueError(
                f"Gmail expected item.binary[{prop!r}] for attachment upload, but it was missing"
            )
        ref = ad.flows.coerce_binary_ref(raw)
        data = await ad.flows.get_binary_stream(ref, context.analytiq_client)
        if not data:
            raise ValueError(f"Gmail attachment {prop!r} is empty")
        out.append(
            OutboundAttachment(
                name=str(ref.file_name or prop),
                content=bytes(data),
                mime_type=str(ref.mime_type or "application/octet-stream"),
            )
        )
    return out
