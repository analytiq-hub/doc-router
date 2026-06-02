"""Outlook node validation and message helpers (ported from n8n Outlook v2)."""

from __future__ import annotations

from typing import Any

SIMPLE_MESSAGE_SELECT = (
    "id,conversationId,subject,bodyPreview,from,toRecipients,categories,hasAttachments"
)


_VALID_OPS: dict[str, frozenset[str]] = {
    "message": frozenset(
        {"send", "get", "getAll", "delete", "move", "reply", "update"}
    ),
    "folder": frozenset({"create", "get", "getAll", "update", "delete"}),
    "draft": frozenset({"create", "get", "delete", "send", "update"}),
    "folderMessage": frozenset({"getAll"}),
    "calendar": frozenset({"create", "get", "getAll", "update", "delete"}),
    "contact": frozenset({"create", "get", "getAll", "update", "delete"}),
    "event": frozenset({"create", "get", "getAll", "update", "delete"}),
    "messageAttachment": frozenset({"add", "get", "getAll", "download"}),
}


def validate_resource_operation(resource: str, operation: str) -> None:
    allowed = _VALID_OPS.get(resource)
    if not allowed:
        raise ValueError(f"Unknown Microsoft Outlook resource: {resource}")
    if operation not in allowed:
        raise ValueError(
            f"Unsupported Microsoft Outlook operation {operation!r} for resource {resource!r}"
        )


def param_str(params: dict[str, Any], key: str, *, default: str = "") -> str:
    val = params.get(key)
    if val is None:
        return default
    return str(val).strip()


def additional_fields(params: dict[str, Any]) -> dict[str, Any]:
    raw = params.get("additionalFields")
    return dict(raw) if isinstance(raw, dict) else {}


def options_dict(params: dict[str, Any]) -> dict[str, Any]:
    raw = params.get("options")
    return dict(raw) if isinstance(raw, dict) else {}


def make_recipient(email: str) -> dict[str, Any]:
    return {"emailAddress": {"address": email.strip()}}


def parse_recipients(value: Any) -> list[dict[str, Any]]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return [make_recipient(str(x)) for x in value if str(x).strip()]
    text = str(value).strip()
    if not text:
        return []
    return [make_recipient(part) for part in text.split(",") if part.strip()]


def create_message(fields: dict[str, Any]) -> dict[str, Any]:
    """Build a Graph ``message`` object from flat / additional field dict."""

    working = dict(fields)
    message: dict[str, Any] = {}

    body_content = working.pop("bodyContent", None)
    body_type = working.pop("bodyContentType", None) or "html"
    if body_content is not None or body_type:
        message["body"] = {
            "content": body_content if body_content is not None else " ",
            "contentType": body_type,
        }

    for key in ("bccRecipients", "ccRecipients", "replyTo", "toRecipients"):
        if key in working:
            message[key] = parse_recipients(working.pop(key))

    for key in ("from", "sender"):
        if key in working and working[key]:
            message[key] = make_recipient(str(working.pop(key)))

    for key, value in working.items():
        if value is None or value == "":
            continue
        message[key] = value
    return message


def simplify_messages(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in rows:
        to_raw = item.get("toRecipients") or []
        to_addrs: list[str] = []
        if isinstance(to_raw, list):
            for rec in to_raw:
                if isinstance(rec, dict):
                    ea = rec.get("emailAddress")
                    if isinstance(ea, dict) and ea.get("address"):
                        to_addrs.append(str(ea["address"]))
        from_addr = None
        fr = item.get("from")
        if isinstance(fr, dict):
            ea = fr.get("emailAddress")
            if isinstance(ea, dict):
                from_addr = ea.get("address")
        out.append(
            {
                "id": item.get("id"),
                "conversationId": item.get("conversationId"),
                "subject": item.get("subject"),
                "bodyPreview": item.get("bodyPreview"),
                "from": from_addr,
                "to": to_addrs,
                "categories": item.get("categories"),
                "hasAttachments": item.get("hasAttachments"),
            }
        )
    return out


def _odata_bool_literal(value: Any) -> bool | None:
    """Parse UI / JSON values for OData boolean filters (``bool('false')`` is true in Python)."""

    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    text = str(value).strip().lower()
    if text in ("true", "1", "yes"):
        return True
    if text in ("false", "0", "no"):
        return False
    return bool(value)


def _message_filter_parts(
    selected: dict[str, Any],
    *,
    include_folders: bool = False,
    include_received_window: bool = False,
) -> list[str]:
    parts: list[str] = []

    if include_folders:
        include = selected.get("foldersToInclude")
        if isinstance(include, list) and include:
            folder_exprs = [
                f"parentFolderId eq '{str(f).replace(chr(39), chr(39) * 2)}'"
                for f in include
                if str(f).strip()
            ]
            if folder_exprs:
                parts.append(f"({' or '.join(folder_exprs)})")
        exclude = selected.get("foldersToExclude")
        if isinstance(exclude, list):
            for folder in exclude:
                fid = str(folder).strip()
                if fid:
                    parts.append(f"parentFolderId ne '{fid.replace(chr(39), chr(39) * 2)}'")

    if selected.get("sender"):
        sender = str(selected["sender"]).replace("'", "''")
        parts.append(
            f"(from/emailAddress/address eq '{sender}' or from/emailAddress/name eq '{sender}')"
        )

    read_status = selected.get("readStatus")
    if read_status and read_status != "both":
        parts.append(f"isRead eq {str(read_status == 'read').lower()}")

    has_att = _odata_bool_literal(selected.get("hasAttachments"))
    if has_att is not None:
        parts.append(f"hasAttachments eq {str(has_att).lower()}")

    if include_received_window:
        if selected.get("receivedAfter"):
            parts.append(f"receivedDateTime ge {selected['receivedAfter']}")
        if selected.get("receivedBefore"):
            parts.append(f"receivedDateTime le {selected['receivedBefore']}")

    if selected.get("custom"):
        parts.append(str(selected["custom"]))

    return parts


def prepare_trigger_filters(filters: Any) -> str | None:
    """OData ``$filter`` from trigger ``filters`` object (n8n ``MessageDescription``)."""

    if not isinstance(filters, dict):
        return None
    parts = _message_filter_parts(filters, include_folders=True)
    return " and ".join(parts) if parts else None


def prepare_filter_string(filters_ui: Any) -> str | None:
    if not isinstance(filters_ui, dict):
        return None
    values = filters_ui.get("values")
    if not isinstance(values, dict):
        return None
    filter_by = values.get("filterBy") or "filters"
    if filter_by == "search":
        search = str(values.get("search") or "").strip()
        return None if not search else None  # search uses $search query param

    selected = values.get("filters")
    if not isinstance(selected, dict):
        selected = values

    parts = _message_filter_parts(selected, include_received_window=True)
    return " and ".join(parts) if parts else None


def list_query(params: dict[str, Any]) -> dict[str, Any]:
    qs: dict[str, Any] = {}
    if params.get("returnAll") in (False, "false", 0, "0"):
        try:
            qs["$top"] = int(params.get("limit") or 50)
        except (TypeError, ValueError):
            qs["$top"] = 50
    filters_ui = params.get("filtersUI")
    if isinstance(filters_ui, dict):
        values = filters_ui.get("values")
        if isinstance(values, dict) and values.get("filterBy") == "search":
            search = str(values.get("search") or "").strip()
            if search:
                qs["$search"] = f'"{search}"'
        else:
            filt = prepare_filter_string(filters_ui)
            if filt:
                qs["$filter"] = filt
    return qs


def message_resource_path(message_id: str, suffix: str = "") -> str:
    """``/messages/{encoded-id}{suffix}`` for Graph message sub-resources."""

    from analytiq_data.flows.integrations.microsoft.graph_api import graph_encode_id

    if suffix and not suffix.startswith("/"):
        suffix = f"/{suffix}"
    return f"/messages/{graph_encode_id(message_id)}{suffix}"


def format_message_output(
    rows: list[dict[str, Any]] | dict[str, Any], params: dict[str, Any]
) -> list[dict[str, Any]] | dict[str, Any]:
    output = param_str(params, "output", default="simple")
    if output == "raw":
        return rows
    if output == "fields":
        names = params.get("fields")
        if isinstance(names, list) and names:
            if isinstance(rows, dict):
                return {k: rows.get(k) for k in names if k in rows}
            return [
                {k: row.get(k) for k in names if k in row}
                for row in rows
                if isinstance(row, dict)
            ]
    if isinstance(rows, dict):
        return simplify_messages([rows])[0]
    return simplify_messages(rows)
