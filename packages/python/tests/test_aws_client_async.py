import asyncio
from unittest.mock import AsyncMock, MagicMock

import aioboto3
import pytest

from analytiq_data.aws.aws_client import AsyncAWSClient


@pytest.mark.asyncio
async def test_refresh_credentials_uses_async_assumed_role_refresh():
    client = AsyncAWSClient(MagicMock(env="test"), "us-east-1")
    client.assumed_role_credentials = MagicMock()
    refresh_calls: list[bool] = []

    async def _refresh_assumed_role_credentials(*, force: bool = False):
        refresh_calls.append(force)

    client._refresh_assumed_role_credentials = _refresh_assumed_role_credentials

    await client.refresh_credentials()

    assert refresh_calls == [False]


@pytest.mark.asyncio
async def test_refresh_credentials_keeps_same_aioboto3_session():
    client = AsyncAWSClient(MagicMock(env="test"), "us-east-1")
    credentials = MagicMock()
    credentials.get_frozen_credentials = AsyncMock()
    credentials._refresh_lock = asyncio.Lock()
    client.assumed_role_credentials = credentials
    session = MagicMock(name="aioboto3_session")
    client.session = session

    await client.refresh_credentials()

    credentials.get_frozen_credentials.assert_awaited_once()
    assert client.session is session


@pytest.mark.asyncio
async def test_refresh_credentials_does_not_mutate_bedrock_config_keys():
    client = AsyncAWSClient(MagicMock(env="test"), "us-east-1")
    client.aws_access_key_id = "bedrock-key"
    client.aws_secret_access_key = "bedrock-secret"
    credentials = MagicMock()
    credentials.get_frozen_credentials = AsyncMock()
    credentials._refresh_lock = asyncio.Lock()
    client.assumed_role_credentials = credentials
    client.session = MagicMock()

    await client.refresh_credentials()

    assert client.aws_access_key_id == "bedrock-key"
    assert client.aws_secret_access_key == "bedrock-secret"


@pytest.mark.asyncio
async def test_aioboto3_session_yields_async_client_context():
    session = aioboto3.Session(
        aws_access_key_id="key",
        aws_secret_access_key="secret",
        region_name="us-east-1",
    )
    cm = session.client("s3")
    assert hasattr(cm, "__aenter__")
    assert type(cm).__name__ == "ClientCreatorContext"


@pytest.mark.asyncio
async def test_init_runs_assumed_role_setup():
    client = AsyncAWSClient(MagicMock(env="test"), "us-east-1")

    async def _aws_config(_client):
        return {"aws_access_key_id": "key", "aws_secret_access_key": "secret"}

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr("analytiq_data.aws.aws_client.get_aws_config", _aws_config)

    setup_calls: list[bool] = []

    async def _setup_assumed_role_session():
        setup_calls.append(True)
        client.session = MagicMock(name="aioboto3_session")

    async def _bucket_name(_client):
        return "test-bucket"

    monkeypatch.setattr(client, "_setup_assumed_role_session", _setup_assumed_role_session)
    monkeypatch.setattr(
        "analytiq_data.aws.aws_client.get_s3_bucket_name",
        _bucket_name,
    )

    await client.init()
    monkeypatch.undo()

    assert setup_calls == [True]
    assert client.s3_bucket_name == "test-bucket"
    assert client.aws_access_key_id == "key"
    assert client.aws_secret_access_key == "secret"
