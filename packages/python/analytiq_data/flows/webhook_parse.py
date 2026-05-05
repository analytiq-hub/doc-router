"""
Parse inbound HTTP requests for ``flows.trigger.webhook`` (see ``docs/docrouter_binary.md`` §4.3).

Splits JSON/text bodies from binary payloads and multipart file fields. File fields yield
pending byte tuples for the caller to upload to GridFS ``flow_blobs`` after ``execution_id`` exists.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import dataclass
from typing import Any
from urllib.parse import unquote

from starlette.datastructures import UploadFile
from starlette.requests import Request

logger = logging.getLogger(__name__)

# RFC 6266 / 5987 — filename and filename* on Content-Disposition (single-part POST bodies).
_RE_CONTENT_DISP_FILENAME_STAR = re.compile(r"filename\*\s*=\s*(?:([^']+)'')?([^;\s]+)", re.IGNORECASE)
_RE_CONTENT_DISP_FILENAME_DQ = re.compile(r'filename\s*=\s*"((?:\\.|[^"\\])*)"', re.IGNORECASE)
_RE_CONTENT_DISP_FILENAME_PLAIN = re.compile(r"filename\s*=\s*([^;\s]+)", re.IGNORECASE)

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


def _webhook_primary_mime(content_type_header: str) -> str:
    return (content_type_header or "").split(";")[0].strip().lower()


def inbound_content_type_allow_unicode_json_body(content_type_header: str) -> bool:
    """
    Request bodies we decode to ``str`` or ``dict`` and place on ``ParsedWebhookBody.body``.

    Many webhook setups route **most** payloads through JSON/form parsing unless **binary data** mode is enabled,
    in which case the entire stream becomes a binary file. DocRouter splits the difference automatically:
    structured JSON / plain / HTML / XML MIME types stay in ``body``; file-like types (CSV, spreadsheets as
    ``text/*`` except plain/html/XML, opaque ``application/*``, etc.) behave like binary mode—the raw bytes go
    to ``pending_binaries`` only.
    """

    primary = _webhook_primary_mime(content_type_header)
    # Unknown / missing — backward compatible: attempt UTF-8 + JSON decode.
    if not primary:
        return True

    # JSON (incl. ``application/vnd.*+json``).
    if "application/json" in primary or primary.endswith("+json"):
        return True

    # XML family (often inspected as Unicode text rather than opaque bytes).
    if primary.endswith("+xml") or primary in ("text/xml", "application/xml"):
        return True

    # Typical small text payloads surfaced in expressions.
    if primary in ("text/plain", "text/html"):
        return True

    return False


def filename_from_content_disposition(content_disposition: str | None) -> str | None:
    """
    Best-effort ``filename`` / ``filename*`` from ``Content-Disposition``.

    Bare ``filename="…"`` without a disposition type (invalid per RFC but common from clients)
    is normalized by prefixing ``attachment; `` before parsing.
    Returns a basename only (no path segments).
    """

    if not content_disposition or not isinstance(content_disposition, str):
        return None
    v = content_disposition.strip()
    if not v:
        return None
    lv = v.lower()
    if not lv.startswith("attachment") and not lv.startswith("inline"):
        v = f"attachment; {v}"

    m = _RE_CONTENT_DISP_FILENAME_STAR.search(v)
    if m:
        raw_fn = (m.group(2) or "").strip().strip('"')
        if raw_fn:
            try:
                name = unquote(raw_fn)
            except Exception:
                name = raw_fn
            return _basename_only(name)

    m = _RE_CONTENT_DISP_FILENAME_DQ.search(v)
    if m:
        inner = m.group(1).replace("\\\"", '"').replace("\\\\", "\\")
        return _basename_only(unquote(inner)) if inner else None

    m = _RE_CONTENT_DISP_FILENAME_PLAIN.search(v)
    if m:
        raw_fn = m.group(1).strip().strip('"')
        if raw_fn:
            return _basename_only(unquote(raw_fn))

    return None


def _basename_only(name: str) -> str:
    s = (name or "").strip()
    if not s or s in (".", ".."):
        return ""
    # Strip path-like prefixes from hostile clients.
    s = s.replace("\\", "/").split("/")[-1].strip()
    return s or ""


def webhook_stashed_body_file_name(request: Request) -> str:
    """
    Non-multipart body stored as binary: ``Content-Disposition`` filename when present,
    otherwise a new random UUID string (no extension).
    """

    fn = filename_from_content_disposition(request.headers.get("content-disposition"))
    if fn:
        return fn
    return str(uuid.uuid4())


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

    mime_top = ct.split(";")[0].strip() or "application/octet-stream"
    body_fname = webhook_stashed_body_file_name(request)

    if raw_body:
        return ParsedWebhookBody(
            query=query,
            body=None,
            form=None,
            pending_binaries=[(bp, raw, mime_top, body_fname)],
            body_stashed_as_binary=True,
        )

    if inbound_content_type_looks_binary(ct):
        return ParsedWebhookBody(
            query=query,
            body=None,
            form=None,
            pending_binaries=[(bp, raw, mime_top, body_fname)],
            body_stashed_as_binary=True,
        )

    if _raw_body_sniffs_opaque_binary(raw):
        return ParsedWebhookBody(
            query=query,
            body=None,
            form=None,
            pending_binaries=[(bp, raw, mime_top, body_fname)],
            body_stashed_as_binary=True,
        )

    if inbound_content_type_allow_unicode_json_body(ct):
        try:
            body = json.loads(raw.decode("utf-8"))
        except Exception:
            logger.debug(f"Inbound webhook body allows UTF-8 but JSON parse failed; using string body (mime={mime_top!r})")
            body = raw.decode("utf-8", errors="replace")
        return ParsedWebhookBody(query=query, body=body, form=None, pending_binaries=[])

    return ParsedWebhookBody(
        query=query,
        body=None,
        form=None,
        pending_binaries=[(bp, raw, mime_top, body_fname)],
        body_stashed_as_binary=True,
    )
