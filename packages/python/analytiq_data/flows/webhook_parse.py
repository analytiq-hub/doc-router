"""
Parse inbound HTTP requests for ``flows.trigger.webhook`` (see ``docs/docrouter_binary.md`` §4.3).

Splits JSON/text bodies from binary payloads and multipart file fields. File fields yield
pending byte tuples for the caller to upload to GridFS ``flow_blobs`` after ``execution_id`` exists.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from starlette.datastructures import UploadFile
from starlette.requests import Request

logger = logging.getLogger(__name__)

_INBOUND_BINARY_CONTENT_TYPE_MARKERS = (
    "application/pdf",
    "image/",
    "audio/",
    "video/",
    "application/zip",
    "application/x-zip-compressed",
    "application/gzip",
    "application/x-gzip",
    "application/octet-stream",
    # OpenDocument, OOXML, EPUB, many proprietary package types (often ZIP-wrapped).
    "application/vnd.",
    "+zip",
)


def inbound_content_type_looks_binary(content_type_header: str) -> bool:
    h = (content_type_header or "").lower()
    # `application/vnd.*+json`, `...+xml`, etc. carry structured text, not package binaries.
    if any(s in h for s in ("+json", "+xml", "+yaml")):
        return False
    return any(marker in h for marker in _INBOUND_BINARY_CONTENT_TYPE_MARKERS)


def _raw_body_sniffs_opaque_binary(raw: bytes) -> bool:
    """
    When ``Content-Type`` is ambiguous, avoid UTF-8 decoding opaque bytes into ``json.body``.

    Heuristics: NUL in the first 64KiB, common archive magics.
    """

    if not raw:
        return False
    head = raw[:65536]
    if b"\x00" in head:
        return True
    if raw.startswith(b"PK\x03\x04") or raw.startswith(b"PK\x05\x06"):
        return True
    if raw.startswith(b"\x1f\x8b"):
        return True
    return False


@dataclass
class ParsedWebhookBody:
    """Payload derived from an inbound webhook HTTP request."""

    query: dict[str, str]
    body: Any
    form: dict[str, str] | None
    pending_binaries: list[tuple[str, bytes, str, str | None]]
    """
    (field_name, raw_bytes, mime_type, original_filename or None).

    Uploaded to ``flow_blobs`` under keys like ``{execution_id}/webhook/incoming/...`` by the route handler.
    """

    body_stashed_as_binary: bool = False
    """True when the raw HTTP body bytes are only in ``pending_binaries`` (not in ``body`` / JSON)."""


async def parse_webhook_request(
    request: Request,
    *,
    raw_body: bool = False,
    binary_property_name: str = "data",
) -> ParsedWebhookBody:
    query = dict(request.query_params)
    ct = request.headers.get("content-type") or ""
    ct_l = ct.lower()
    bp = (binary_property_name or "").strip() or "data"

    if request.method in ("GET", "HEAD"):
        return ParsedWebhookBody(query=query, body=None, form=None, pending_binaries=[])

    if "multipart/form-data" in ct_l:
        fldata = await request.form()
        form_fields: dict[str, str] = {}
        pending: list[tuple[str, bytes, str, str | None]] = []
        for key, val in fldata.multi_items():
            if isinstance(val, UploadFile):
                raw = await val.read()
                fname = val.filename or key
                mime = val.content_type or "application/octet-stream"
                pending.append((key, raw, mime, fname))
            else:
                prev = form_fields.get(key)
                merged = "" if prev is None else f"{prev},"
                form_fields[key] = merged + str(val)
        return ParsedWebhookBody(
            query=query,
            body=None,
            form=form_fields if form_fields else None,
            pending_binaries=pending,
        )

    if "application/x-www-form-urlencoded" in ct_l:
        fldata = await request.form()
        form_fields = {}
        pending = []
        for key, val in fldata.multi_items():
            if isinstance(val, UploadFile):
                raw = await val.read()
                fname = val.filename or key
                mime = val.content_type or "application/octet-stream"
                pending.append((key, raw, mime, fname))
            else:
                prev = form_fields.get(key)
                merged = "" if prev is None else f"{prev},"
                form_fields[key] = merged + str(val)
        return ParsedWebhookBody(
            query=query,
            body=None,
            form=form_fields if form_fields else None,
            pending_binaries=pending,
        )

    raw = await request.body()
    if not raw:
        return ParsedWebhookBody(query=query, body=None, form=None, pending_binaries=[])

    if raw_body:
        mime = ct.split(";")[0].strip() or "application/octet-stream"
        return ParsedWebhookBody(
            query=query,
            body=None,
            form=None,
            pending_binaries=[(bp, raw, mime, None)],
            body_stashed_as_binary=True,
        )

    if "application/json" in ct_l:
        try:
            body = json.loads(raw.decode("utf-8"))
        except Exception:
            logger.debug("Inbound webhook claimed JSON but parse failed; using string body")
            body = raw.decode("utf-8", errors="replace")
        return ParsedWebhookBody(query=query, body=body, form=None, pending_binaries=[])

    if inbound_content_type_looks_binary(ct):
        mime = ct.split(";")[0].strip() or "application/octet-stream"
        return ParsedWebhookBody(
            query=query,
            body=None,
            form=None,
            pending_binaries=[(bp, raw, mime, None)],
            body_stashed_as_binary=True,
        )

    if _raw_body_sniffs_opaque_binary(raw):
        mime = ct.split(";")[0].strip() or "application/octet-stream"
        return ParsedWebhookBody(
            query=query,
            body=None,
            form=None,
            pending_binaries=[(bp, raw, mime, None)],
            body_stashed_as_binary=True,
        )

    try:
        body = json.loads(raw.decode("utf-8"))
    except Exception:
        body = raw.decode("utf-8", errors="replace")

    return ParsedWebhookBody(query=query, body=body, form=None, pending_binaries=[])
