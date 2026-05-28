"""Shared helpers for ``flows.microsoft_onedrive``."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote, unquote

_ONEDRIVE_ID_FROM_URL_RE = re.compile(
    r"https://onedrive\.live\.com/.*?(?:\?|&)id=([^&]+)",
    re.IGNORECASE,
)
_ONEDRIVE_RESID_FROM_URL_RE = re.compile(
    r"https://onedrive\.live\.com/.*?(?:\?|&)resid=([^&]+)",
    re.IGNORECASE,
)

_VALID_OPS: dict[str, frozenset[str]] = {
    "file": frozenset(
        {"copy", "delete", "download", "get", "rename", "search", "share", "upload"}
    ),
    "folder": frozenset(
        {"create", "delete", "getChildren", "rename", "search", "share"}
    ),
}


def validate_resource_operation(resource: str, operation: str) -> None:
    allowed = _VALID_OPS.get(resource)
    if not allowed:
        raise ValueError(f"Unknown Microsoft OneDrive resource: {resource}")
    if operation not in allowed:
        raise ValueError(
            f"Unsupported Microsoft OneDrive operation {operation!r} for resource {resource!r}"
        )


def search_query_path(query: str) -> str:
    """OData search segment for ``/drive/root/search(q='...')``."""

    escaped = str(query or "").replace("'", "''")
    return f"/drive/root/search(q='{escaped}')"


def encoded_drive_item_path(parent_id: str, file_name: str) -> str:
    return f"/drive/items/{parent_id}:/{quote(str(file_name), safe='')}:/content"


def normalize_onedrive_watch_id(raw: Any) -> str:
    """Drive item id from plain id or ``onedrive.live.com`` URL (n8n resource locator parity)."""

    s = unquote(str(raw or "").strip())
    if not s:
        return ""
    s = s.replace("%21", "!")
    for pattern in (_ONEDRIVE_ID_FROM_URL_RE, _ONEDRIVE_RESID_FROM_URL_RE):
        m = pattern.search(s)
        if m:
            return unquote(m.group(1)).replace("%21", "!")
    return s


def simplify_onedrive_item(item: dict[str, Any]) -> dict[str, Any]:
    fs = item.get("fileSystemInfo") if isinstance(item.get("fileSystemInfo"), dict) else {}
    parent = item.get("parentReference") if isinstance(item.get("parentReference"), dict) else {}
    file_meta = item.get("file") if isinstance(item.get("file"), dict) else {}
    return {
        "id": item.get("id"),
        "createdDateTime": fs.get("createdDateTime"),
        "lastModifiedDateTime": fs.get("lastModifiedDateTime"),
        "name": item.get("name"),
        "webUrl": item.get("webUrl"),
        "size": item.get("size"),
        "path": parent.get("path") or "",
        "mimeType": file_meta.get("mimeType") or "",
    }
