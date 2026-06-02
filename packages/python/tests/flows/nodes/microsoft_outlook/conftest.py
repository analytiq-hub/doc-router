"""Shared fixtures for ``flows.microsoft_outlook`` unit tests."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

import analytiq_data as ad

_OL = "analytiq_data.flows.nodes.microsoft_outlook"
_OPS = f"{_OL}.operations"


@pytest.fixture
def outlook_ctx() -> ad.flows.ExecutionContext:
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
def outlook_item() -> ad.flows.FlowItem:
    return ad.flows.FlowItem(json={"row": 1}, binary={}, meta={})


@pytest.fixture
def outlook_node_shell() -> dict[str, Any]:
    return {
        "id": "n1",
        "name": "Microsoft Outlook",
        "type": "flows.microsoft_outlook",
        "credentials": {"microsoftOutlookOAuth2Api": "cred-1"},
    }


@pytest.fixture
def mock_outlook_auth():
    with patch(
        f"{_OPS}.resolve_outlook_auth",
        new_callable=AsyncMock,
        return_value=("tok", {"useShared": False}, "https://graph.microsoft.com/v1.0/me"),
    ) as m:
        yield m


@pytest.fixture
def mock_outlook_request():
    with patch(f"{_OPS}.outlook_request", new_callable=AsyncMock) as m:
        yield m
