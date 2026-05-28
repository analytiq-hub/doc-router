"""OneDrive node helpers (product-specific dispatch; shared drive utils in integrations)."""

from __future__ import annotations

from typing import Any

from analytiq_data.flows.integrations.microsoft import normalize_drive_item_id

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


def onedrive_item_id(params: dict[str, Any], key: str) -> str:
    return normalize_drive_item_id(params.get(key))
