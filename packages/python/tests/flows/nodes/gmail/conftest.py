"""Shared fixtures for ``flows.gmail`` unit tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

import analytiq_data as ad

_GMAIL = "analytiq_data.flows.nodes.gmail"
_OPS = f"{_GMAIL}.operations"


def gmail_schema_path() -> Path:
    return (
        Path(__file__).resolve().parents[4]
        / "analytiq_data"
        / "flows"
        / "nodes"
        / "gmail"
        / "parameter.schema.json"
    )


@pytest.fixture
def gmail_schema() -> dict[str, Any]:
    return json.loads(gmail_schema_path().read_text(encoding="utf-8"))


@pytest.fixture
def gmail_ctx() -> ad.flows.ExecutionContext:
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
def gmail_item() -> ad.flows.FlowItem:
    return ad.flows.FlowItem(json={"row": 1}, binary={}, meta={})


@pytest.fixture
def gmail_node_shell() -> dict[str, Any]:
    return {
        "id": "n1",
        "name": "Gmail",
        "type": "flows.gmail",
        "credentials": {"gmailOAuth2": "cred-1"},
    }


@pytest.fixture
def mock_gmail_token():
    with patch(f"{_OPS}.resolve_oauth_access_token", new_callable=AsyncMock, return_value="tok") as m:
        yield m


@pytest.fixture
def mock_gmail_api():
    with patch(f"{_OPS}.gmail_api_request", new_callable=AsyncMock) as m:
        yield m


@pytest.fixture
def mock_gmail_api_all():
    with patch(f"{_OPS}.gmail_api_request_all_items", new_callable=AsyncMock) as m:
        yield m
