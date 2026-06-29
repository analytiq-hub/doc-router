import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import aioboto3
import pytest

from analytiq_data.aws.aws_client import AsyncAWSClient


@pytest.mark.asyncio
async def test_refresh_credentials_noop_without_assumed_role_credentials():
    client = AsyncAWSClient(MagicMock(env="test"), "us-east-1")
    client.assumed_role_credentials = None

    refresh = AsyncMock()
    client._refresh_assumed_role_credentials = refresh

    await client.refresh_credentials()

    refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_refresh_credentials_delegates_non_force_refresh():
    client = AsyncAWSClient(MagicMock(env="test"), "us-east-1")
    client.assumed_role_credentials = MagicMock()
    refresh = AsyncMock()
    client._refresh_assumed_role_credentials = refresh

    await client.refresh_credentials()

    refresh.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_refresh_assumed_role_credentials_advisory_path():
    client = AsyncAWSClient(MagicMock(env="test"), "us-east-1")
    credentials = MagicMock()
    credentials.get_frozen_credentials = AsyncMock()
    credentials._refresh_lock = asyncio.Lock()
    client.assumed_role_credentials = credentials

    await client._refresh_assumed_role_credentials(force=False)

    credentials.get_frozen_credentials.assert_awaited_once()
    credentials._protected_refresh.assert_not_called()


@pytest.mark.asyncio
async def test_refresh_assumed_role_credentials_force_path():
    client = AsyncAWSClient(MagicMock(env="test"), "us-east-1")
    credentials = MagicMock()
    credentials.get_frozen_credentials = AsyncMock()
    credentials._protected_refresh = AsyncMock()
    credentials._refresh_lock = asyncio.Lock()
    client.assumed_role_credentials = credentials

    await client._refresh_assumed_role_credentials(force=True)

    credentials._protected_refresh.assert_awaited_once_with(is_mandatory=True)
    credentials.get_frozen_credentials.assert_not_awaited()


@pytest.mark.asyncio
async def test_refresh_credentials_keeps_same_aioboto3_session():
    client = AsyncAWSClient(MagicMock(env="test"), "us-east-1")
    session = MagicMock(name="aioboto3_session")
    client.session = session
    client.assumed_role_credentials = MagicMock()
    client._refresh_assumed_role_credentials = AsyncMock()

    await client.refresh_credentials()

    client._refresh_assumed_role_credentials.assert_awaited_once_with()
    assert client.session is session


@pytest.mark.asyncio
async def test_refresh_credentials_does_not_mutate_bedrock_config_keys():
    client = AsyncAWSClient(MagicMock(env="test"), "us-east-1")
    client.aws_access_key_id = "bedrock-key"
    client.aws_secret_access_key = "bedrock-secret"
    client.assumed_role_credentials = MagicMock()
    client._refresh_assumed_role_credentials = AsyncMock()

    await client.refresh_credentials()

    assert client.aws_access_key_id == "bedrock-key"
    assert client.aws_secret_access_key == "bedrock-secret"


@pytest.mark.asyncio
async def test_sts_client_creator_passes_source_keys_and_region():
    client = AsyncAWSClient(MagicMock(env="test"), "us-east-1")
    client.aws_access_key_id = "source-key"
    client.aws_secret_access_key = "source-secret"
    client.region_name = "us-west-2"

    aio_sessions: list[MagicMock] = []

    def _make_aio_session():
        session = MagicMock()
        aio_sessions.append(session)
        return session

    with patch.object(client, "_resolve_assume_role_arn", AsyncMock(return_value="arn:role")):
        with patch(
            "analytiq_data.aws.aws_client.aiobotocore.session.AioSession",
            side_effect=_make_aio_session,
        ):
            with patch(
                "analytiq_data.aws.aws_client.AioDeferredRefreshableCredentials",
            ) as creds_cls:
                creds = MagicMock()
                creds.get_frozen_credentials = AsyncMock()
                creds_cls.return_value = creds
                with patch(
                    "analytiq_data.aws.aws_client.AioAssumeRoleCredentialFetcher",
                ) as fetcher_cls:
                    fetcher_cls.return_value.fetch_credentials = MagicMock()
                    await client._setup_assumed_role_session()

    source_session = aio_sessions[0]
    sts_client_creator = fetcher_cls.call_args.kwargs["client_creator"]
    sts_client_creator(
        "sts",
        aws_access_key_id="source-key",
        aws_secret_access_key="source-secret",
    )

    source_session.create_client.assert_called_once_with(
        "sts",
        region_name="us-west-2",
        aws_access_key_id="source-key",
        aws_secret_access_key="source-secret",
    )


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


@pytest.mark.asyncio
async def test_init_falls_back_to_config_keys_when_assume_role_fails():
    client = AsyncAWSClient(MagicMock(env="test"), "us-east-1")

    async def _aws_config(_client):
        return {"aws_access_key_id": "key", "aws_secret_access_key": "secret"}

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr("analytiq_data.aws.aws_client.get_aws_config", _aws_config)

    async def _setup_fail():
        raise RuntimeError("assume role failed")

    async def _bucket_name(_client):
        return "fallback-bucket"

    monkeypatch.setattr(client, "_setup_assumed_role_session", _setup_fail)
    monkeypatch.setattr(
        "analytiq_data.aws.aws_client.get_s3_bucket_name",
        _bucket_name,
    )

    await client.init()
    monkeypatch.undo()

    assert client.assumed_role_credentials is None
    assert client.session is not None
    assert client.s3_bucket_name == "fallback-bucket"
