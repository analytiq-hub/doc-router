from __future__ import annotations

"""Google Drive trigger poll logic (n8n ``GoogleDriveTrigger`` parity)."""

from datetime import datetime, UTC
from typing import Any

import analytiq_data as ad

from .api import (
    GoogleDriveApiError,
    google_api_request,
    google_api_request_all_items,
    resolve_oauth_access_token_for_org,
)
from .helpers import DRIVE_FOLDER_MIME, normalize_drive_watch_id

LAST_TIME_CHECKED_KEY = "last_time_checked"


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def build_drive_trigger_query(
    *,
    trigger_on: str,
    event: str,
    folder_id: str,
    options: dict[str, Any],
    start_date: str | None,
    apply_time_filter: bool,
) -> str:
    """Build Drive ``files.list`` ``q`` string (mirrors n8n ``GoogleDriveTrigger.poll``)."""

    query = ["trashed = false"]

    if trigger_on == "specificFolder" and event != "watchFolderUpdated" and folder_id:
        query.append(f"'{folder_id}' in parents")

    if event.startswith("file"):
        query.append(f"mimeType != '{DRIVE_FOLDER_MIME}'")
    else:
        query.append(f"mimeType = '{DRIVE_FOLDER_MIME}'")

    file_type = options.get("fileType")
    if file_type and file_type != "all":
        query.append(f"mimeType = '{file_type}'")

    if apply_time_filter and start_date:
        if "Created" in event:
            query.append(f"createdTime > '{start_date}'")
        else:
            query.append(f"modifiedTime > '{start_date}'")

    return " and ".join(query)


def _filter_files_for_trigger(
    files: list[dict[str, Any]],
    *,
    trigger_on: str,
    event: str,
    file_id: str,
    folder_id: str,
    apply_post_filter: bool,
) -> list[dict[str, Any]]:
    if not apply_post_filter:
        return files

    if trigger_on == "specificFile" and file_id:
        return [f for f in files if str(f.get("id") or "") == file_id]

    if trigger_on == "specificFolder" and event == "watchFolderUpdated" and folder_id:
        return [f for f in files if str(f.get("id") or "") == folder_id]

    return files


async def _verify_watch_resource(
    token: str,
    *,
    trigger_on: str,
    file_id: str,
    folder_id: str,
) -> None:
    """Activation smoke test: credential can read the configured file/folder."""

    resource_id = file_id if trigger_on == "specificFile" else folder_id
    label = "fileToWatch" if trigger_on == "specificFile" else "folderToWatch"
    try:
        await google_api_request(
            token,
            "GET",
            f"/drive/v3/files/{resource_id}",
            query={"fields": "id", "supportsAllDrives": True},
        )
    except GoogleDriveApiError as e:
        if e.status_code == 404:
            raise ad.flows.FlowValidationError(
                f"Google Drive {label}: resource not found or not accessible ({resource_id!r}). "
                "Enter a valid folder/file ID or share URL and ensure the credential can access it."
            ) from e
        raise


async def poll_google_drive_trigger(
    context: "ad.flows.PollContext",
    node: dict[str, Any],
) -> list[list[ad.flows.FlowItem]] | None:
    """
    Poll Google Drive for changes and return one item per matching file metadata dict.

    Updates ``context.static_data[last_time_checked]`` before returning (n8n order).
    """

    params = node.get("parameters") if isinstance(node.get("parameters"), dict) else {}
    trigger_on = str(params.get("triggerOn") or "").strip()
    event = str(params.get("event") or "").strip()
    options = params.get("options") if isinstance(params.get("options"), dict) else {}

    if trigger_on not in ("specificFile", "specificFolder"):
        raise ValueError(f"triggerOn must be specificFile or specificFolder, got {trigger_on!r}")
    if not event:
        raise ValueError("event is required")

    file_id = normalize_drive_watch_id(params.get("fileToWatch"))
    folder_id = normalize_drive_watch_id(params.get("folderToWatch"))

    if trigger_on == "specificFile" and not file_id:
        raise ad.flows.FlowValidationError(
            "fileToWatch is required (Google Drive file ID or share URL)"
        )
    if trigger_on == "specificFolder" and not folder_id:
        raise ad.flows.FlowValidationError(
            "folderToWatch is required (Google Drive folder ID or share URL)"
        )

    manual = context.mode == "manual"
    testing = bool(context.tick_meta.get("testing"))
    apply_time_filter = not manual and not testing

    now = _utc_now_iso()
    start_date = context.get_static(LAST_TIME_CHECKED_KEY) or now

    token = await resolve_oauth_access_token_for_org(context.organization_id, node)

    if testing:
        await _verify_watch_resource(
            token,
            trigger_on=trigger_on,
            file_id=file_id,
            folder_id=folder_id,
        )
        context.set_static(LAST_TIME_CHECKED_KEY, now)
        return None

    qs: dict[str, Any] = {
        "includeItemsFromAllDrives": True,
        "supportsAllDrives": True,
        "spaces": "appDataFolder, drive",
        "corpora": "allDrives",
        "q": build_drive_trigger_query(
            trigger_on=trigger_on,
            event=event,
            folder_id=folder_id,
            options=options,
            start_date=start_date,
            apply_time_filter=apply_time_filter,
        ),
        "fields": "nextPageToken, files(*)",
    }

    if manual:
        qs["pageSize"] = 1
        data = await google_api_request(token, "GET", "/drive/v3/files", query=qs)
        raw_files = data.get("files") if isinstance(data, dict) else []
        files = [f for f in raw_files if isinstance(f, dict)] if isinstance(raw_files, list) else []
    else:
        files = await google_api_request_all_items(
            None,
            token,
            "GET",
            "/drive/v3/files",
            "files",
            query=qs,
        )

    files = _filter_files_for_trigger(
        files,
        trigger_on=trigger_on,
        event=event,
        file_id=file_id,
        folder_id=folder_id,
        apply_post_filter=apply_time_filter,
    )

    context.set_static(LAST_TIME_CHECKED_KEY, now)

    if not files:
        if manual:
            raise ad.flows.FlowValidationError(
                "No data with the current filter could be found"
            )
        return None

    out: list[ad.flows.FlowItem] = []
    for i, file_meta in enumerate(files):
        out.append(
            ad.flows.FlowItem(
                json=dict(file_meta),
                binary={},
                meta={"source_node_id": node["id"], "item_index": i},
                paired_item=None,
            )
        )
    return [out]
