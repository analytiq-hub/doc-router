"""SharePoint node helpers (resource/operation dispatch)."""

from __future__ import annotations

from typing import Any

from analytiq_data.flows.integrations.microsoft import (
    normalize_drive_item_id,
    normalize_site_id,
)

_VALID_OPS: dict[str, frozenset[str]] = {
    "file": frozenset(
        {"copy", "delete", "download", "get", "rename", "search", "share", "upload"}
    ),
    "folder": frozenset(
        {"create", "delete", "getChildren", "rename", "search", "share"}
    ),
    "list": frozenset({"get", "getItems", "getMany"}),
    "site": frozenset({"get", "search"}),
}


def validate_resource_operation(resource: str, operation: str) -> None:
    allowed = _VALID_OPS.get(resource)
    if not allowed:
        raise ValueError(f"Unknown Microsoft SharePoint resource: {resource}")
    if operation not in allowed:
        raise ValueError(
            f"Unsupported Microsoft SharePoint operation {operation!r} "
            f"for resource {resource!r}"
        )


def sharepoint_item_id(params: dict[str, Any], key: str) -> str:
    return normalize_drive_item_id(params.get(key))


def sharepoint_site_id(params: dict[str, Any]) -> str:
    return normalize_site_id(params.get("siteId"))
