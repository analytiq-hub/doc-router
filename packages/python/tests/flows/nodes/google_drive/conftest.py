"""Shared fixtures for ``flows.google_drive`` unit tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

import analytiq_data as ad

_GD = "analytiq_data.flows.nodes.google_drive"
_OPS = f"{_GD}.operations"
_API = f"{_GD}.api"


def google_drive_schema_path() -> Path:
    return (
        Path(__file__).resolve().parents[4]
        / "analytiq_data"
        / "flows"
        / "nodes"
        / "google_drive"
        / "parameter.schema.json"
    )


@pytest.fixture
def drive_schema() -> dict[str, Any]:
    return json.loads(google_drive_schema_path().read_text(encoding="utf-8"))


@pytest.fixture
def drive_ctx() -> ad.flows.ExecutionContext:
    return ad.flows.ExecutionContext(
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


@pytest.fixture
def drive_item() -> ad.flows.FlowItem:
    return ad.flows.FlowItem(json={"row": 1}, binary={}, meta={"trace": "t1"})


@pytest.fixture
def drive_node_shell() -> dict[str, Any]:
    return {
        "id": "n1",
        "name": "Google Drive",
        "type": "flows.google_drive",
        "credentials": {"googleDriveOAuth2Api": "cred-1"},
    }


@pytest.fixture
def mock_oauth_token():
    with patch(f"{_OPS}.resolve_oauth_access_token", new_callable=AsyncMock, return_value="tok") as m:
        yield m


@pytest.fixture
def mock_gd_api():
    with patch(f"{_OPS}.google_api_request", new_callable=AsyncMock) as m:
        yield m


@pytest.fixture
def mock_gd_api_all_items():
    with patch(f"{_OPS}.google_api_request_all_items", new_callable=AsyncMock) as m:
        yield m
