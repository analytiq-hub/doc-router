"""Microsoft OneDrive trigger poll logic (n8n ``MicrosoftOneDriveTrigger`` parity)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import analytiq_data as ad

from .api import (
    MicrosoftGraphApiError,
    format_onedrive_graph_error,
    get_onedrive_folder_path,
    microsoft_graph_request,
    microsoft_graph_request_all_items_delta,
    resolve_oauth_access_token_for_org,
)
from .helpers import normalize_onedrive_watch_id, simplify_onedrive_item

LAST_TIME_CHECKED_KEY = "last_time_checked"
LAST_LINK_KEY = "last_link"
_DELTA_LATEST = "https://graph.microsoft.com/v1.0/me/drive/root/delta?token=latest"
_DELTA_ROOT = "https://graph.microsoft.com/v1.0/me/drive/root/delta"


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _event_type_and_resource(event: str) -> tuple[str, str]:
    event_type = "updated" if "Updated" in event else "created"
    event_resource = "folder" if "folder" in event else "file"
    return event_type, event_resource


def _raise_poll_graph_error(exc: MicrosoftGraphApiError) -> None:
    raise ad.flows.FlowValidationError(format_onedrive_graph_error(exc)) from exc


async def _probe_onedrive_delta_sync(
    token: str,
    *,
    trace_node_id: str | None,
) -> None:
    """Ensure delta tracking works (required for the trigger; ``/me/drive`` alone is not enough)."""

    page = await microsoft_graph_request(
        token,
        "GET",
        "",
        url=_DELTA_LATEST,
        trace_node_id=trace_node_id,
    )
    if isinstance(page, dict) and page.get("@odata.deltaLink"):
        return


async def poll_microsoft_onedrive_trigger(
    context: "ad.flows.PollContext",
    node: dict[str, Any],
) -> list[list[ad.flows.FlowItem]] | None:
    params = node.get("parameters") if isinstance(node.get("parameters"), dict) else {}
    event = str(params.get("event") or "fileCreated").strip()
    watch = str(params.get("watch") or "").strip()
    watch_folder = bool(params.get("watchFolder"))
    options = params.get("options") if isinstance(params.get("options"), dict) else {}
    folder_child = bool(options.get("folderChild"))
    simplify = bool(params.get("simple", True))

    if event == "fileUpdated" and not watch:
        watch = "anyFile"
    if event == "folderUpdated" and not watch:
        watch = "anyFolder"

    event_type, event_resource = _event_type_and_resource(event)
    manual = context.mode == "manual"
    testing = bool(context.tick_meta.get("testing"))

    now = _utc_now_iso()
    start = str(context.get_static(LAST_TIME_CHECKED_KEY) or now)
    last_link = str(context.get_static(LAST_LINK_KEY) or _DELTA_LATEST)

    token = await resolve_oauth_access_token_for_org(context.organization_id, node)
    trace_id = context.node_id

    try:
        if testing:
            await _probe_onedrive_delta_sync(token, trace_node_id=trace_id)
            file_id = normalize_onedrive_watch_id(params.get("fileId"))
            folder_id = normalize_onedrive_watch_id(params.get("folderId"))
            if watch == "selectedFile" and file_id:
                await microsoft_graph_request(
                    token, "GET", f"/drive/items/{file_id}", trace_node_id=trace_id
                )
            elif folder_id and (
                watch in ("selectedFolder", "oneSelectedFolder") or watch_folder
            ):
                await get_onedrive_folder_path(None, token, folder_id, trace_node_id=trace_id)
            context.set_static(LAST_TIME_CHECKED_KEY, now)
            context.set_static(LAST_LINK_KEY, last_link)
            return None

        if manual:
            page = await microsoft_graph_request(
                token,
                "GET",
                "",
                url=_DELTA_ROOT,
                trace_node_id=trace_id,
            )
            raw = page.get("value") if isinstance(page, dict) else []
            response_data = (
                [x for x in raw if isinstance(x, dict)] if isinstance(raw, list) else []
            )
        else:
            delta_link, response_data = await microsoft_graph_request_all_items_delta(
                None,
                token,
                last_link,
                start,
                event_type,
                trace_node_id=trace_id,
            )
            if delta_link:
                context.set_static(LAST_LINK_KEY, delta_link)
    except MicrosoftGraphApiError as e:
        _raise_poll_graph_error(e)

    context.set_static(LAST_TIME_CHECKED_KEY, now)

    file_id = normalize_onedrive_watch_id(params.get("fileId"))
    folder_id = normalize_onedrive_watch_id(params.get("folderId"))

    if watch == "selectedFile" and file_id:
        response_data = [x for x in response_data if str(x.get("id") or "") == file_id]

    if (
        not folder_child
        and (watch in ("oneSelectedFolder", "selectedFolder") or watch_folder)
        and folder_id
    ):
        if watch == "oneSelectedFolder":
            response_data = [x for x in response_data if str(x.get("id") or "") == folder_id]
        else:
            response_data = [
                x
                for x in response_data
                if isinstance(x.get("parentReference"), dict)
                and str((x.get("parentReference") or {}).get("id") or "") == folder_id
            ]

    if folder_child and (watch == "selectedFolder" or watch_folder) and folder_id:
        folder_path = await get_onedrive_folder_path(
            None, token, folder_id, trace_node_id=trace_id
        )
        filtered: list[dict[str, Any]] = []
        for item in response_data:
            parent = item.get("parentReference")
            path = ""
            if isinstance(parent, dict):
                path = str(parent.get("path") or "")
            if isinstance(path, str) and path.startswith(folder_path):
                filtered.append(item)
        response_data = filtered

    response_data = [x for x in response_data if x.get(event_resource)]

    if not response_data:
        if manual:
            raise ad.flows.FlowValidationError(
                "No data with the current filter could be found"
            )
        return None

    if simplify:
        response_data = [simplify_onedrive_item(x) for x in response_data]

    out: list[ad.flows.FlowItem] = []
    for i, row in enumerate(response_data):
        out.append(
            ad.flows.FlowItem(
                json=dict(row),
                binary={},
                meta={"source_node_id": node["id"], "item_index": i},
                paired_item=None,
            )
        )
    return [out]
