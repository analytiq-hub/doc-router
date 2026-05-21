"""Shared helpers for ``flows.google_drive``."""

from __future__ import annotations

import json
from typing import Any

RLC_DRIVE_DEFAULT = "My Drive"
RLC_FOLDER_DEFAULT = "root"

DRIVE_FOLDER_MIME = "application/vnd.google-apps.folder"

_VALID_OPS: dict[str, frozenset[str]] = {
    "drive": frozenset({"create", "deleteDrive", "get", "list", "update"}),
    "file": frozenset(
        {
            "copy",
            "createFromText",
            "deleteFile",
            "download",
            "move",
            "share",
            "update",
            "upload",
        }
    ),
    "fileFolder": frozenset({"search"}),
    "folder": frozenset({"create", "deleteFolder", "share"}),
}


def validate_resource_operation(resource: str, operation: str) -> None:
    allowed = _VALID_OPS.get(resource)
    if not allowed or operation not in allowed:
        raise ValueError(f'Unknown Google Drive resource/operation: {resource}/{operation}')


def rlc_value(raw: Any, *, default: str = "") -> str:
    """Extract a resource-locator or plain string parameter."""

    if raw is None:
        return default
    if isinstance(raw, dict):
        val = raw.get("value")
        return str(val) if val is not None else default
    if isinstance(raw, str):
        s = raw.strip()
        if s.startswith("{"):
            try:
                obj = json.loads(s)
            except json.JSONDecodeError:
                return s or default
            if isinstance(obj, dict) and "value" in obj:
                return str(obj["value"]) if obj["value"] is not None else default
        return s or default
    return str(raw)


def set_parent_folder(
    folder_id: str,
    drive_id: str,
    *,
    folder_default: str = RLC_FOLDER_DEFAULT,
    drive_default: str = RLC_DRIVE_DEFAULT,
) -> str:
    if folder_id and folder_id != folder_default:
        return folder_id
    if drive_id and drive_id != drive_default:
        return drive_id
    return "root"


def update_drive_scopes(
    qs: dict[str, Any],
    drive_id: str,
    *,
    drive_default: str = RLC_DRIVE_DEFAULT,
) -> None:
    if not drive_id:
        return
    if drive_id == drive_default:
        qs["includeItemsFromAllDrives"] = False
        qs["supportsAllDrives"] = False
        qs["spaces"] = "appDataFolder, drive"
        qs["corpora"] = "user"
    else:
        qs["driveId"] = drive_id
        qs["corpora"] = "drive"


def shared_drive_query_defaults() -> dict[str, Any]:
    return {
        "includeItemsFromAllDrives": True,
        "supportsAllDrives": True,
        "spaces": "appDataFolder, drive",
        "corpora": "allDrives",
    }


def prepare_query_fields(fields: Any) -> str:
    if isinstance(fields, list):
        if "*" in fields:
            return "*"
        return ", ".join(str(x) for x in fields if str(x).strip())
    return "id, name"


def set_file_properties(body: dict[str, Any], options: dict[str, Any]) -> dict[str, Any]:
    props_ui = options.get("propertiesUi")
    if isinstance(props_ui, dict):
        rows = props_ui.get("propertyValues")
        if isinstance(rows, list):
            props: dict[str, Any] = {}
            for row in rows:
                if isinstance(row, dict) and row.get("key") is not None:
                    props[str(row["key"])] = row.get("value")
            if props:
                body["properties"] = props
    app_ui = options.get("appPropertiesUi")
    if isinstance(app_ui, dict):
        rows = app_ui.get("appPropertyValues")
        if isinstance(rows, list):
            app_props: dict[str, Any] = {}
            for row in rows:
                if isinstance(row, dict) and row.get("key") is not None:
                    app_props[str(row["key"])] = row.get("value")
            if app_props:
                body["appProperties"] = app_props
    return body


def set_update_common_params(qs: dict[str, Any], options: dict[str, Any]) -> dict[str, Any]:
    if options.get("keepRevisionForever"):
        qs["keepRevisionForever"] = True
    if options.get("ocrLanguage"):
        qs["ocrLanguage"] = options["ocrLanguage"]
    if options.get("useContentAsIndexableText"):
        qs["useContentAsIndexableText"] = True
    return qs


def permissions_from_ui(permissions_ui: Any) -> list[dict[str, Any]]:
    if not isinstance(permissions_ui, dict):
        return []
    rows = permissions_ui.get("permissionsValues")
    if not isinstance(rows, list):
        return []
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        body: dict[str, Any] = {}
        for key in ("role", "type", "emailAddress", "domain", "allowFileDiscovery"):
            if row.get(key) is not None and row.get(key) != "":
                body[key] = row[key]
        if body:
            out.append(body)
    return out


def share_options_query(options: dict[str, Any]) -> dict[str, Any]:
    qs: dict[str, Any] = {"supportsAllDrives": True}
    for key in (
        "emailMessage",
        "moveToNewOwnersRoot",
        "sendNotificationEmail",
        "transferOwnership",
        "useDomainAdminAccess",
    ):
        if key in options and options[key] not in (None, ""):
            qs[key] = options[key]
    return qs
