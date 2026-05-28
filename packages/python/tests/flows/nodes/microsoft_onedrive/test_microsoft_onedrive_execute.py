from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import analytiq_data as ad
import pytest


@pytest.mark.asyncio
async def test_node_execute_file_get(
    onedrive_ctx: ad.flows.ExecutionContext,
    onedrive_item: ad.flows.FlowItem,
    onedrive_node_shell: dict[str, Any],
) -> None:
    ad.flows.register_builtin_nodes()
    nt = ad.flows.get("flows.microsoft_onedrive")
    node = {
        **onedrive_node_shell,
        "parameters": {"resource": "file", "operation": "get", "fileId": "item-1"},
    }
    with (
        patch(
            "analytiq_data.flows.nodes.microsoft_onedrive.operations.resolve_oauth_access_token",
            new_callable=AsyncMock,
            return_value="tok",
        ),
        patch(
            "analytiq_data.flows.nodes.microsoft_onedrive.operations._graph",
            new_callable=AsyncMock,
            return_value={"id": "item-1", "file": {}, "name": "doc.pdf"},
        ),
    ):
        out = await nt.execute(onedrive_ctx, node, [[onedrive_item]])
    assert len(out[0]) == 1
    assert out[0][0].json["name"] == "doc.pdf"
