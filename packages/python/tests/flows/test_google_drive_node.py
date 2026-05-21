from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

import analytiq_data as ad


def _register_nodes() -> None:
    ad.flows.register_builtin_nodes()


@pytest.fixture
def schema() -> dict:
    path = (
        Path(__file__).resolve().parents[2]
        / "analytiq_data"
        / "flows"
        / "nodes"
        / "google_drive"
        / "parameter.schema.json"
    )
    return json.loads(path.read_text(encoding="utf-8"))


def test_google_drive_node_is_experimental() -> None:
    _register_nodes()
    nt = ad.flows.get("flows.google_drive")
    assert getattr(nt, "experimental", False) is True
    assert nt.type_version == 3


def test_parameter_schema_merges_operations(schema: dict) -> None:
    op = schema["properties"]["operation"]
    assert "x-ui-enum-by" in op
    assert "upload" in op["enum"]
    assert "search" in op["enum"]


@pytest.mark.asyncio
async def test_drive_get_calls_api() -> None:
    _register_nodes()
    nt = ad.flows.get("flows.google_drive")
    node = {
        "id": "n1",
        "name": "Drive",
        "type": "flows.google_drive",
        "parameters": {
            "authentication": "oAuth2",
            "resource": "drive",
            "operation": "get",
            "driveId": "abc123",
        },
        "credentials": {"googleDriveOAuth2Api": "cred-1"},
    }
    item = ad.flows.FlowItem(json={}, binary={}, meta={})
    ctx = ad.flows.ExecutionContext(
        execution_id="e1",
        flow_id="f1",
        flow_revid="r1",
        organization_id="org1",
        mode="manual",
        trigger_data={},
        run_data={},
        revision_nodes=[],
        credentials={},
        analytiq_client=None,
    )

    with (
        patch(
            "analytiq_data.flows.nodes.google_drive.operations.resolve_oauth_access_token",
            new_callable=AsyncMock,
            return_value="tok",
        ),
        patch(
            "analytiq_data.flows.nodes.google_drive.operations.google_api_request",
            new_callable=AsyncMock,
            return_value={"id": "abc123", "name": "Team Drive"},
        ) as mock_req,
    ):
        out = await nt.execute(ctx, node, [[item]])
    assert len(out[0]) == 1
    assert out[0][0].json["name"] == "Team Drive"
    mock_req.assert_awaited_once()
    assert mock_req.await_args.args[2] == "/drive/v3/drives/abc123"
