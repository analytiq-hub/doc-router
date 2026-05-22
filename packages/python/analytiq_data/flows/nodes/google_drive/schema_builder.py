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
    if "fileId" in ordered:
        fid = ordered["fileId"]
        if isinstance(fid, dict):
            fid["title"] = "File"
            fid["description"] = (
                "Google Drive file ID, or paste a Google Docs/Drive link "
                "(the ID is taken from the URL when you run the flow)."
            )
            fid["x-ui-placeholder"] = (
                "e.g. 1QLUu--7KcnD5HNeY7NaOhtSQV-EH8US7UrtNkM7zigA or https://docs.google.com/document/d/…/edit"
            )

    return {"type": "object", "properties": ordered, "additionalProperties": False}


def write_parameter_schema(description: dict[str, Any], path: Path | None = None) -> Path:
    target = path or _SCHEMA_PATH
    schema = build_google_drive_parameter_schema(description)
    target.write_text(json.dumps(schema, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return target
