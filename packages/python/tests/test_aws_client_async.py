import asyncio
from unittest.mock import MagicMock

import pytest

from analytiq_data.aws.aws_client import AsyncAWSClient


@pytest.mark.asyncio
async def test_refresh_credentials_runs_refresh_off_event_loop(monkeypatch):
    client = AsyncAWSClient(MagicMock(env="test"), "us-east-1")
    client.botocore_session = MagicMock()
    refresh_calls: list[bool] = []

    def _refresh_credentials_sync(*, force: bool = False):
        refresh_calls.append(force)

    client._refresh_credentials_sync = _refresh_credentials_sync

    to_thread_targets: list[object] = []

    async def _mock_to_thread(func, *args, **kwargs):
        to_thread_targets.append(func)
        return func(*args, **kwargs)

    monkeypatch.setattr(asyncio, "to_thread", _mock_to_thread)

    await client.refresh_credentials()

    assert refresh_calls == [False]
    assert to_thread_targets == [_refresh_credentials_sync]


@pytest.mark.asyncio
async def test_refresh_credentials_keeps_same_aioboto3_session(monkeypatch):
    client = AsyncAWSClient(MagicMock(env="test"), "us-east-1")
    client.botocore_session = MagicMock()
    credentials = MagicMock()
    client.botocore_session.get_credentials.return_value = credentials
    session = MagicMock(name="aioboto3_session")
    client.session = session

    async def _mock_to_thread(func, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr(asyncio, "to_thread", _mock_to_thread)

    await client.refresh_credentials()

    credentials.get_frozen_credentials.assert_called_once()
    assert client.session is session


@pytest.mark.asyncio
async def test_init_runs_assumed_role_setup_off_event_loop(monkeypatch):
    client = AsyncAWSClient(MagicMock(env="test"), "us-east-1")

    async def _aws_config(_client):
        return {"aws_access_key_id": "key", "aws_secret_access_key": "secret"}

    monkeypatch.setattr("analytiq_data.aws.aws_client.get_aws_config", _aws_config)

    setup_calls: list[bool] = []

    def _setup_assumed_role_session_sync():
        setup_calls.append(True)
        client.session = MagicMock(name="aioboto3_session")

    async def _mock_to_thread(func, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr(asyncio, "to_thread", _mock_to_thread)
    monkeypatch.setattr(client, "_setup_assumed_role_session_sync", _setup_assumed_role_session_sync)

    async def _bucket_name(_client):
        return "test-bucket"

    monkeypatch.setattr(
        "analytiq_data.aws.aws_client.get_s3_bucket_name",
        _bucket_name,
    )

    await client.init()

    assert setup_calls == [True]
    assert client.s3_bucket_name == "test-bucket"
