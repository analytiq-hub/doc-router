"""Build ``parameter.schema.json`` for ``flows.google_drive`` from an integration dump row."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from analytiq_data.flows.port.schema import build_top_level_parameter_schema

_SCHEMA_PATH = Path(__file__).resolve().parent / "parameter.schema.json"
_TOP_KEYS = ("resource", "operation")
# Shown immediately under Operation (before the merged ``options`` blob).
_AFTER_OPERATION_KEYS = (
    "fileId",
    "folderNoRootId",
    "sameFolder",
    "folderId",
    "driveId",
    "name",
    "content",
    "inputDataFieldName",
    "newUpdatedFileName",
    "changeFileContent",
    "permissionsUi",
    "searchMethod",
    "queryString",
    "filter",
    "returnAll",
    "limit",
)
_TAIL_KEYS = ("options",)

_FILE_ID_DESC = (
    "Enter a Google Drive file ID or paste a Docs/Drive share link "
    "(the ID is taken from the URL when the flow runs)."
)
_FILE_ID_PLACEHOLDER = (
    "File ID or https://docs.google.com/document/d/…/edit"
)
_FOLDER_WATCH_DESC = (
    "Enter a Google Drive folder ID or paste a folder link "
    "(the ID is taken from the URL when the flow runs)."
)
_FOLDER_WATCH_PLACEHOLDER = "Folder ID or https://drive.google.com/drive/folders/…"
_FOLDER_ID_DESC = "Parent folder in Google Drive. Use root for My Drive, or enter a folder ID."
_FOLDER_ID_PLACEHOLDER = "root or folder ID"
_FOLDER_NO_ROOT_DESC = "Google Drive folder ID (cannot be root)."
_FOLDER_NO_ROOT_PLACEHOLDER = "Folder ID"
_DRIVE_ID_DESC = "Shared drive ID (from the drive URL or Google Admin)."
_DRIVE_ID_PLACEHOLDER = "Shared drive ID"


def _set_string_field_hints(
    prop: dict[str, Any] | None,
    *,
    title: str,
    description: str,
    placeholder: str,
) -> None:
    if not isinstance(prop, dict):
        return
    prop["title"] = title
    prop["description"] = description
    prop["x-ui-placeholder"] = placeholder


def _enrich_drive_resource_fields(ordered: dict[str, Any]) -> None:
    _set_string_field_hints(
        ordered.get("fileId"),
        title="File",
        description=_FILE_ID_DESC,
        placeholder=_FILE_ID_PLACEHOLDER,
    )
    _set_string_field_hints(
        ordered.get("folderId"),
        title="Folder",
        description=_FOLDER_ID_DESC,
        placeholder=_FOLDER_ID_PLACEHOLDER,
    )
    _set_string_field_hints(
        ordered.get("folderNoRootId"),
        title="Folder",
        description=_FOLDER_NO_ROOT_DESC,
        placeholder=_FOLDER_NO_ROOT_PLACEHOLDER,
    )
    _set_string_field_hints(
        ordered.get("driveId"),
        title="Shared Drive",
        description=_DRIVE_ID_DESC,
        placeholder=_DRIVE_ID_PLACEHOLDER,
    )


def build_google_drive_parameter_schema(description: dict[str, Any]) -> dict[str, Any]:
    """OAuth2-only schema: ``resource`` / ``operation`` first, no ``authentication``."""

    raw = build_top_level_parameter_schema(description)
    props = raw.get("properties") if isinstance(raw.get("properties"), dict) else {}
    ordered: dict[str, Any] = {}
    for key in _TOP_KEYS:
        if key in props:
            ordered[key] = props[key]
    for key in _AFTER_OPERATION_KEYS:
        if key in props:
            ordered[key] = props[key]
    for key in _TAIL_KEYS:
        if key in props:
            ordered[key] = props[key]
    for key, val in props.items():
        if key not in ordered:
            ordered[key] = val

    if "operation" in ordered:
        op = ordered["operation"]
        if isinstance(op, dict):
            op["default"] = "upload"
            op["title"] = "Operation"
    if "resource" in ordered:
        res = ordered["resource"]
        if isinstance(res, dict):
            res["title"] = "Resource"
    _enrich_drive_resource_fields(ordered)

    return {"type": "object", "properties": ordered, "additionalProperties": False}


def write_parameter_schema(description: dict[str, Any], path: Path | None = None) -> Path:
    target = path or _SCHEMA_PATH
    schema = build_google_drive_parameter_schema(description)
    target.write_text(json.dumps(schema, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return target
