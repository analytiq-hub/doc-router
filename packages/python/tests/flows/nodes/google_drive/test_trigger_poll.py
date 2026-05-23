"""Unit tests for Google Drive trigger poll logic."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

import analytiq_data as ad

from analytiq_data.flows.nodes.google_drive.poll_trigger import (
    LAST_TIME_CHECKED_KEY,
    build_drive_trigger_query,
    poll_google_drive_trigger,
)

_GD = "analytiq_data.flows.nodes.google_drive.poll_trigger"


def test_build_query_folder_file_created_with_time_filter() -> None:
    q = build_drive_trigger_query(
        trigger_on="specificFolder",
        event="fileCreated",
        folder_id="folder-1",
        options={},
        start_date="2026-05-21T10:00:00+00:00",
        apply_time_filter=True,
    )
    assert "'folder-1' in parents" in q
    assert "mimeType != 'application/vnd.google-apps.folder'" in q
    assert "createdTime > '2026-05-21T10:00:00+00:00'" in q


def test_build_query_folder_updated_uses_modified_time() -> None:
    q = build_drive_trigger_query(
        trigger_on="specificFolder",
        event="fileUpdated",
        folder_id="folder-1",
        options={},
        start_date="2026-05-21T10:00:00+00:00",
        apply_time_filter=True,
    )
    assert "modifiedTime > '2026-05-21T10:00:00+00:00'" in q


def test_build_query_watch_folder_skips_parents_clause() -> None:
    q = build_drive_trigger_query(
        trigger_on="specificFolder",
        event="watchFolderUpdated",
        folder_id="folder-1",
        options={},
        start_date="2026-05-21T10:00:00+00:00",
        apply_time_filter=True,
    )
    assert "in parents" not in q
    assert "mimeType = 'application/vnd.google-apps.folder'" in q


def test_build_query_file_type_filter() -> None:
    q = build_drive_trigger_query(
        trigger_on="specificFolder",
        event="fileCreated",
        folder_id="folder-1",
        options={"fileType": "application/vnd.google-apps.document"},
        start_date=None,
        apply_time_filter=False,
    )
    assert "mimeType = 'application/vnd.google-apps.document'" in q


def _poll_ctx(
    *,
    mode: str = "schedule",
    testing: bool = False,
    static: dict | None = None,
) -> ad.flows.PollContext:
    return ad.flows.PollContext(
        organization_id="org1",
        flow_id="flow1",
        flow_revid="rev1",
        node_id="gd1",
        mode=mode,  # type: ignore[arg-type]
        analytiq_client=None,
        tick_meta={"testing": testing} if testing else {},
        static_data=dict(static or {}),
    )


def _node(params: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": "gd1",
        "name": "Google Drive Trigger",
        "type": "flows.trigger.google_drive",
        "credentials": {"googleDriveOAuth2Api": "cred-1"},
        "parameters": params,
    }


@pytest.mark.asyncio
async def test_poll_specific_folder_enqueues_items() -> None:
    ctx = _poll_ctx(static={"last_time_checked": "2026-05-21T09:00:00+00:00"})
    node = _node(
        {
            "triggerOn": "specificFolder",
            "event": "fileCreated",
            "folderToWatch": "folder-1",
            "options": {},
        }
    )
    files = [{"id": "f1", "name": "New doc"}]
    with patch(f"{_GD}.resolve_oauth_access_token_for_org", new_callable=AsyncMock, return_value="tok"):
        with patch(f"{_GD}.google_api_request_all_items", new_callable=AsyncMock, return_value=files) as m:
            out = await poll_google_drive_trigger(ctx, node)
    assert out is not None
    assert len(out[0]) == 1
    assert out[0][0].json["id"] == "f1"
    assert ctx.get_static(LAST_TIME_CHECKED_KEY)
    qs = m.await_args.kwargs["query"]
    assert "'folder-1' in parents" in qs["q"]


@pytest.mark.asyncio
async def test_poll_specific_file_filters_to_watched_file() -> None:
    ctx = _poll_ctx(static={"last_time_checked": "2026-05-21T09:00:00+00:00"})
    node = _node(
        {
            "triggerOn": "specificFile",
            "event": "fileUpdated",
            "fileToWatch": "target-file",
            "options": {},
        }
    )
    files = [
        {"id": "other", "name": "Other"},
        {"id": "target-file", "name": "Target"},
    ]
    with patch(f"{_GD}.resolve_oauth_access_token_for_org", new_callable=AsyncMock, return_value="tok"):
        with patch(f"{_GD}.google_api_request_all_items", new_callable=AsyncMock, return_value=files):
            out = await poll_google_drive_trigger(ctx, node)
    assert out is not None
    assert len(out[0]) == 1
    assert out[0][0].json["id"] == "target-file"


@pytest.mark.asyncio
async def test_poll_empty_schedule_returns_none() -> None:
    ctx = _poll_ctx(static={"last_time_checked": "2026-05-21T09:00:00+00:00"})
    node = _node(
        {
            "triggerOn": "specificFolder",
            "event": "fileCreated",
            "folderToWatch": "folder-1",
        }
    )
    with patch(f"{_GD}.resolve_oauth_access_token_for_org", new_callable=AsyncMock, return_value="tok"):
        with patch(f"{_GD}.google_api_request_all_items", new_callable=AsyncMock, return_value=[]):
            out = await poll_google_drive_trigger(ctx, node)
    assert out is None


@pytest.mark.asyncio
async def test_poll_manual_no_data_raises() -> None:
    ctx = _poll_ctx(mode="manual")
    node = _node(
        {
            "triggerOn": "specificFolder",
            "event": "fileCreated",
            "folderToWatch": "folder-1",
        }
    )
    with patch(f"{_GD}.resolve_oauth_access_token_for_org", new_callable=AsyncMock, return_value="tok"):
        with patch(f"{_GD}.google_api_request", new_callable=AsyncMock, return_value={"files": []}):
            with pytest.raises(ad.flows.FlowValidationError, match="No data"):
                await poll_google_drive_trigger(ctx, node)


@pytest.mark.asyncio
async def test_poll_activation_testing_verifies_resource() -> None:
    ctx = _poll_ctx(testing=True)
    node = _node(
        {
            "triggerOn": "specificFolder",
            "event": "fileCreated",
            "folderToWatch": "folder-1",
        }
    )
    with patch(f"{_GD}.resolve_oauth_access_token_for_org", new_callable=AsyncMock, return_value="tok"):
        with patch(f"{_GD}.google_api_request", new_callable=AsyncMock, return_value={"id": "folder-1"}) as m:
            with patch(f"{_GD}.google_api_request_all_items", new_callable=AsyncMock) as list_m:
                out = await poll_google_drive_trigger(ctx, node)
    assert out is None
    m.assert_awaited_once()
    assert m.await_args.args[2] == "/drive/v3/files/folder-1"
    list_m.assert_not_awaited()


@pytest.mark.asyncio
async def test_poll_rejects_invalid_folder_id_before_api() -> None:
    ctx = _poll_ctx(testing=True)
    node = _node(
        {
            "triggerOn": "specificFolder",
            "event": "fileCreated",
            "folderToWatch": ".",
        }
    )
    with pytest.raises(ad.flows.FlowValidationError, match="folderToWatch is required"):
        await poll_google_drive_trigger(ctx, node)


@pytest.mark.asyncio
async def test_poll_activation_testing_allows_empty() -> None:
    ctx = _poll_ctx(testing=True)
    node = _node(
        {
            "triggerOn": "specificFolder",
            "event": "fileCreated",
            "folderToWatch": "folder-1",
        }
    )
    with patch(f"{_GD}.resolve_oauth_access_token_for_org", new_callable=AsyncMock, return_value="tok"):
        with patch(f"{_GD}.google_api_request", new_callable=AsyncMock, return_value={"id": "folder-1"}):
            out = await poll_google_drive_trigger(ctx, node)
    assert out is None


@pytest.mark.asyncio
async def test_trigger_node_execute_replays_items() -> None:
    ad.flows.register_builtin_nodes()
    nt = ad.flows.get("flows.trigger.google_drive")
    ctx = ad.flows.ExecutionContext(
        organization_id="org1",
        execution_id="e1",
        flow_id="f1",
        flow_revid="r1",
        mode="schedule",
        trigger_data={
            "type": "poll",
            "items": [[{"json": {"id": "f1"}, "binary": {}, "meta": {}, "paired_item": None}]],
        },
        run_data={},
        analytiq_client=None,
    )
    node = {"id": "gd1", "name": "GD", "type": "flows.trigger.google_drive", "parameters": {}}
    out = await nt.execute(ctx, node, [[]])
    assert out[0][0].json["id"] == "f1"
