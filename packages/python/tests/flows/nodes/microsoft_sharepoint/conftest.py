"""Shared fixtures for ``flows.microsoft_sharepoint`` unit tests."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

import analytiq_data as ad

_SP = "analytiq_data.flows.nodes.microsoft_sharepoint"
_OPS = f"{_SP}.operations"


@pytest.fixture
def sharepoint_ctx() -> ad.flows.ExecutionContext:
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
def sharepoint_item() -> ad.flows.FlowItem:
    return ad.flows.FlowItem(json={"row": 1}, binary={}, meta={})


@pytest.fixture
def sharepoint_node_shell() -> dict[str, Any]:
    return {
        "id": "n1",
        "name": "Microsoft SharePoint",
        "type": "flows.microsoft_sharepoint",
        "credentials": {"microsoftSharePointOAuth2Api": "cred-1"},
    }


@pytest.fixture
def mock_oauth_token():
    with patch(f"{_OPS}.resolve_oauth_access_token", new_callable=AsyncMock, return_value="tok") as m:
        yield m


@pytest.fixture
def mock_graph_api():
    with patch(f"{_OPS}._graph", new_callable=AsyncMock) as m:
        yield m
