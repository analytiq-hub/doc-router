from __future__ import annotations

from typing import Any

import analytiq_data as ad
import pytest

from analytiq_data.flows.nodes.google_drive.operations import execute_google_drive_item


@pytest.mark.asyncio
async def test_search_builds_name_query(
    drive_ctx: ad.flows.ExecutionContext,
    drive_item: ad.flows.FlowItem,
    drive_node_shell: dict[str, Any],
    mock_oauth_token,
    mock_gd_api,
) -> None:
    mock_gd_api.return_value = {"files": [{"id": "f1", "name": "Budget"}]}
    params = {
        "resource": "fileFolder",
        "operation": "search",
        "searchMethod": "name",
        "queryString": "Budget",
        "filter": {"whatToSearch": "files", "includeTrashed": False},
        "limit": 25,
    }
    out = await execute_google_drive_item(drive_ctx, drive_node_shell, params, drive_item, item_index=0)
    assert out.json["files"][0]["name"] == "Budget"
    qs = mock_gd_api.await_args.kwargs["query"]
    assert "name contains 'Budget'" in qs["q"]
    assert "trashed = false" in qs["q"]
    assert mock_gd_api.await_args.args[2] == "/drive/v3/files"


@pytest.mark.asyncio
async def test_search_return_all_uses_pagination_helper(
    drive_ctx: ad.flows.ExecutionContext,
    drive_item: ad.flows.FlowItem,
    drive_node_shell: dict[str, Any],
    mock_oauth_token,
    mock_gd_api_all_items,
) -> None:
    mock_gd_api_all_items.return_value = [{"id": "f1"}, {"id": "f2"}]
    params: dict[str, Any] = {
        "resource": "fileFolder",
        "operation": "search",
        "searchMethod": "query",
        "queryString": "mimeType = 'application/pdf'",
        "returnAll": True,
        "filter": {},
    }
    out = await execute_google_drive_item(drive_ctx, drive_node_shell, params, drive_item, item_index=0)
    assert out.json["files"] == [{"id": "f1"}, {"id": "f2"}]
    mock_gd_api_all_items.assert_awaited_once()
