from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import analytiq_data as ad
import pytest

from analytiq_data.flows.nodes.microsoft_sharepoint.helpers import validate_resource_operation
from analytiq_data.flows.nodes.microsoft_sharepoint.operations import execute_microsoft_sharepoint_item

_OPS = "analytiq_data.flows.nodes.microsoft_sharepoint.operations"


def test_validate_resource_operation_rejects_unknown() -> None:
    with pytest.raises(ValueError, match="Unknown"):
        validate_resource_operation("unknown", "get")


@pytest.mark.asyncio
async def test_execute_file_get(
    sharepoint_ctx: ad.flows.ExecutionContext,
    sharepoint_item: ad.flows.FlowItem,
    sharepoint_node_shell: dict[str, Any],
) -> None:
    with (
        patch(f"{_OPS}.resolve_oauth_access_token", new_callable=AsyncMock, return_value="tok"),
        patch(
            f"{_OPS}.resolve_sharepoint_subdomain",
            new_callable=AsyncMock,
            return_value="contoso",
        ),
        patch(
            f"{_OPS}._graph",
            new_callable=AsyncMock,
            return_value={"id": "item-1", "file": {}, "name": "doc.pdf"},
        ),
    ):
        out = await execute_microsoft_sharepoint_item(
            sharepoint_ctx,
            sharepoint_node_shell,
            {
                "siteId": "root",
                "resource": "file",
                "operation": "get",
                "fileId": "item-1",
            },
            sharepoint_item,
            item_index=0,
        )
    assert out.json["name"] == "doc.pdf"


@pytest.mark.asyncio
async def test_execute_list_get_many(
    sharepoint_ctx: ad.flows.ExecutionContext,
    sharepoint_item: ad.flows.FlowItem,
    sharepoint_node_shell: dict[str, Any],
) -> None:
    with (
        patch(f"{_OPS}.resolve_oauth_access_token", new_callable=AsyncMock, return_value="tok"),
        patch(
            f"{_OPS}.resolve_sharepoint_subdomain",
            new_callable=AsyncMock,
            return_value="contoso",
        ),
        patch(
            f"{_OPS}.graph_request_all_items",
            new_callable=AsyncMock,
            return_value=[{"id": "list-1", "displayName": "Documents"}],
        ),
    ):
        out = await execute_microsoft_sharepoint_item(
            sharepoint_ctx,
            sharepoint_node_shell,
            {
                "siteId": "root",
                "resource": "list",
                "operation": "getMany",
            },
            sharepoint_item,
            item_index=0,
        )
    assert out.json["value"][0]["displayName"] == "Documents"
