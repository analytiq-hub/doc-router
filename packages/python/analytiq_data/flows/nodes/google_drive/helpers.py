"""Shared helpers for ``flows.google_drive``."""

from __future__ import annotations

import json
import re
from typing import Any

_DRIVE_FILE_ID_RE = re.compile(
    r"(?:/d/|/file/d/|id=)([a-zA-Z0-9_-]{10,})",
    re.IGNORECASE,
)
_DRIVE_FOLDER_ID_RE = re.compile(
    r"/folders/([a-zA-Z0-9_-]{2,})",
    re.IGNORECASE,
)
_DRIVE_WATCH_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{2,}$")

RLC_DRIVE_DEFAULT = "My Drive"
RLC_FOLDER_DEFAULT = "root"

DRIVE_FOLDER_MIME = "application/vnd.google-apps.folder"

# n8n Google Drive v2/v3 download.operation.ts execute() defaults (per Google app subtype).
_EXPORT_DEFAULT_BY_SUBTYPE: dict[str, str] = {
    "document": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "presentation": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "spreadsheet": "text/csv",
    "drawing": "image/jpeg",
}

_FORMAT_FIELD_BY_SUBTYPE: dict[str, str] = {
    "document": "docsToFormat",
    "presentation": "slidesToFormat",
    "spreadsheet": "sheetsToFormat",
    "drawing": "drawingsToFormat",
}

# Lighter export formats when the primary export hits Google's size limit.
_EXPORT_FALLBACK_BY_SUBTYPE: dict[str, list[str]] = {
    "document": ["text/html", "text/plain", "application/rtf"],
    "presentation": ["application/pdf"],
    "spreadsheet": ["application/vnd.oasis.opendocument.spreadsheet"],
    "drawing": ["image/png", "application/pdf"],
}

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


def google_app_subtype(google_mime: str) -> str:
    """Subtype from ``application/vnd.google-apps.<subtype>`` (e.g. ``document``)."""

    prefix = "application/vnd.google-apps."
    if not google_mime.startswith(prefix):
        return ""
    return google_mime[len(prefix) :].strip()


def _google_file_conversion_map(options: dict[str, Any]) -> dict[str, Any]:
    """``options.googleFileConversion.conversion`` object from the node UI."""

    gfc = options.get("googleFileConversion")
    if not isinstance(gfc, dict):
        return {}
    conv = gfc.get("conversion")
    return conv if isinstance(conv, dict) else {}


def export_mime_for_google_app(google_mime: str, options: dict[str, Any]) -> str:
    """
    Export MIME for a native Google file (matches n8n v2 download execute defaults).
    """

    subtype = google_app_subtype(google_mime)
    conv = _google_file_conversion_map(options)
    field = _FORMAT_FIELD_BY_SUBTYPE.get(subtype)
    if field:
        chosen = conv.get(field)
        if isinstance(chosen, str) and chosen.strip():
            return chosen.strip()
    return _EXPORT_DEFAULT_BY_SUBTYPE.get(subtype, "application/pdf")


def export_fallback_mimes(google_mime: str, primary: str) -> list[str]:
    """Additional export MIME types to try after ``exportSizeLimitExceeded``."""

    subtype = google_app_subtype(google_mime)
    out: list[str] = []
    for mime in _EXPORT_FALLBACK_BY_SUBTYPE.get(subtype, []):
        if mime != primary and mime not in out:
            out.append(mime)
    return out


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


def drive_file_id_from_param(raw: Any) -> str:
    """Normalize ``fileId``: plain ID, or extract from Docs/Drive share URLs."""

    s = rlc_value(raw).strip()
    if not s:
        return ""
    if "://" in s or "/" in s:
        m = _DRIVE_FILE_ID_RE.search(s)
        if m:
            return m.group(1)
        m = _DRIVE_FOLDER_ID_RE.search(s)
        if m:
            return m.group(1)
    return s


def normalize_drive_watch_id(raw: Any) -> str:
    """
    Parse a poll-trigger watch target (RLC, plain id, or share URL).

    Returns ``""`` when missing or not a plausible Drive file/folder id.
    """

    s = drive_file_id_from_param(raw).strip()
    if not s or s in (".", ".."):
        return ""
    if "://" in s or "/" in s:
        return ""
    if not _DRIVE_WATCH_ID_RE.fullmatch(s):
        return ""
    return s


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
