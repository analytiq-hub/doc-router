from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import analytiq_data as ad
import pytest

from analytiq_data.flows.nodes.microsoft_onedrive.helpers import search_query_path
from analytiq_data.flows.nodes.microsoft_onedrive.operations import execute_microsoft_onedrive_item

_OPS = "analytiq_data.flows.nodes.microsoft_onedrive.operations"


@pytest.mark.asyncio
async def test_file_get(
    onedrive_ctx: ad.flows.ExecutionContext,
    onedrive_item: ad.flows.FlowItem,
    onedrive_node_shell: dict[str, Any],
    mock_oauth_token: AsyncMock,
) -> None:
    params = {"resource": "file", "operation": "get", "fileId": "abc"}
    with patch(f"{_OPS}._graph", new_callable=AsyncMock, return_value={"id": "abc", "name": "x.txt"}) as m:
        out = await execute_microsoft_onedrive_item(
            onedrive_ctx, onedrive_node_shell, params, onedrive_item, item_index=0
        )
    assert out.json["name"] == "x.txt"
    m.assert_awaited_once()
    assert m.await_args.args[2] == "GET"
    assert m.await_args.args[3] == "/drive/items/abc"


@pytest.mark.asyncio
async def test_folder_get_children(
    onedrive_ctx: ad.flows.ExecutionContext,
    onedrive_item: ad.flows.FlowItem,
    onedrive_node_shell: dict[str, Any],
    mock_oauth_token: AsyncMock,
) -> None:
    params = {"resource": "folder", "operation": "getChildren", "folderId": "folder1"}
    children = [{"id": "c1", "name": "child"}]
    with patch(
        f"{_OPS}.microsoft_graph_request_all_items",
        new_callable=AsyncMock,
        return_value=children,
    ):
        out = await execute_microsoft_onedrive_item(
            onedrive_ctx, onedrive_node_shell, params, onedrive_item, item_index=0
        )
    assert out.json["value"] == children


def test_search_query_path_escapes_quotes() -> None:
    assert "''" in search_query_path("foo'bar")
