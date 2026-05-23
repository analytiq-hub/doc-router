"""Shared helpers for ``flows.gmail``."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

_OPS_BY_RESOURCE: dict[str, frozenset[str]] = {
    "message": frozenset(
        {
            "send",
            "get",
            "getAll",
            "reply",
            "delete",
            "markAsRead",
            "markAsUnread",
            "addLabels",
            "removeLabels",
        }
    ),
    "label": frozenset({"create", "delete", "get", "getAll"}),
    "draft": frozenset({"create", "get", "getAll", "delete"}),
    "thread": frozenset(
        {
            "get",
            "getAll",
            "delete",
            "trash",
            "untrash",
            "addLabels",
            "removeLabels",
            "reply",
        }
    ),
}


def validate_resource_operation(resource: str, operation: str) -> None:
    allowed = _OPS_BY_RESOURCE.get(resource)
    if allowed is None:
        raise ValueError(f"Unsupported Gmail resource: {resource!r}")
    if operation not in allowed:
        raise ValueError(f"Unsupported Gmail {resource} operation: {operation!r}")


def prepare_emails_input(raw: str, field_name: str) -> str:
    """Format comma-separated addresses for MIME headers (n8n ``prepareEmailsInput``)."""

    parts: list[str] = []
    for entry in (raw or "").split(","):
        email = entry.strip()
        if not email:
            continue
        if "@" not in email:
            raise ValueError(f"Invalid email address in {field_name!r}: {email!r}")
        if "<" in email and ">" in email:
            parts.append(email)
        else:
            parts.append(f"<{email}>")
    return ", ".join(parts)


def prepare_message_body(params: dict[str, Any]) -> tuple[str | None, str | None]:
    email_type = str(params.get("emailType") or "html")
    body = str(params.get("message") or "")
    if email_type == "text":
        return body, None
    return None, body


def header_from_payload(payload: dict[str, Any], name: str) -> str | None:
    headers = payload.get("headers")
    if isinstance(headers, list):
        for header in headers:
            if isinstance(header, dict) and header.get("name") == name:
                val = header.get("value")
                return str(val) if val is not None else None
    return None


def coerce_label_ids(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if x is not None and str(x).strip()]
    if isinstance(raw, str):
        return [part.strip() for part in raw.split(",") if part.strip()]
    return []


def _append_gmail_query(q: str | None, fragment: str) -> str:
    base = (q or "").strip()
    if base:
        return f"{base} {fragment}".strip()
    return fragment


def prepare_gmail_list_query(filters: dict[str, Any] | None) -> dict[str, Any]:
    """
    Map UI ``filters`` object to Gmail messages.list query params.

    Mirrors n8n ``prepareQuery`` for list/getAll (without node context).
    """

    filters = dict(filters or {})
    qs: dict[str, Any] = {}

    for key in ("includeSpamTrash", "labelIds"):
        if key in filters and filters[key] not in (None, "", []):
            qs[key] = filters[key]

    q_parts: list[str] = []
    base_q = str(filters.get("q") or "").strip()
    if base_q:
        q_parts.append(base_q)

    sender = str(filters.get("sender") or "").strip()
    if sender:
        q_parts.append(f"from:{sender}")

    read_status = str(filters.get("readStatus") or "both").strip()
    if read_status and read_status != "both":
        q_parts.append(f"is:{read_status}")

    for label in ("receivedAfter", "receivedBefore"):
        raw = filters.get(label)
        if raw is None or raw == "":
            continue
        ts = _coerce_unix_seconds(raw)
        if ts is None:
            continue
        word = "after" if label == "receivedAfter" else "before"
        q_parts.append(f"{word}:{ts}")

    if q_parts:
        qs["q"] = " ".join(q_parts)
    return qs


def _coerce_unix_seconds(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        n = int(value)
        if n > 1_000_000_000_000:
            n = n // 1000
        return n
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        if s.isdigit():
            n = int(s)
            if len(s) >= 13:
                n = n // 1000
            return n
        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            return int(dt.timestamp())
        except ValueError:
            return None
    return None


def flatten_message_headers(message: dict[str, Any]) -> dict[str, Any]:
    """Promote ``payload.headers`` onto the top-level JSON (n8n ``simplifyOutput`` subset)."""

    out = dict(message)
    payload = out.get("payload")
    if isinstance(payload, dict):
        headers = payload.get("headers")
        if isinstance(headers, list):
            for header in headers:
                if isinstance(header, dict):
                    name = header.get("name")
                    value = header.get("value")
                    if isinstance(name, str) and name:
                        out[name] = value
    return out


async def simplify_messages(
    token: str,
    messages: list[dict[str, Any]],
    *,
    label_map: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Replace ``labelIds`` with ``labels`` name objects when ``label_map`` is provided."""

    out: list[dict[str, Any]] = []
    for msg in messages:
        row = flatten_message_headers(msg)
        ids = row.get("labelIds")
        if label_map and isinstance(ids, list):
            row["labels"] = [
                {"id": lid, "name": label_map.get(str(lid), str(lid))}
                for lid in ids
                if lid is not None
            ]
            del row["labelIds"]
        out.append(row)
    return out
