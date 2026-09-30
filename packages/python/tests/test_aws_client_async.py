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


@pytest.mark.asyncio
async def test_init_uses_default_chain_when_no_config_keys():
    client = AsyncAWSClient(MagicMock(env="test"), "us-east-1")

    async def _aws_config(_client):
        return {"aws_access_key_id": "", "aws_secret_access_key": ""}

    async def _bucket_name(_client):
        return "profile-bucket"

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr("analytiq_data.aws.aws_client.get_aws_config", _aws_config)
    monkeypatch.setattr(
        "analytiq_data.aws.aws_client.get_s3_bucket_name",
        _bucket_name,
    )

    chain_setup = AsyncMock()
    assume_setup = AsyncMock()
    monkeypatch.setattr(client, "_setup_default_chain_session", chain_setup)
    monkeypatch.setattr(client, "_setup_assumed_role_session", assume_setup)

    await client.init()
    monkeypatch.undo()

    chain_setup.assert_awaited_once()
    assume_setup.assert_not_awaited()
    assert client.assumed_role_credentials is None
    assert client.s3_bucket_name == "profile-bucket"


def _sts_client_context(enter_result=None, enter_error=None):
    cm = MagicMock()

    async def _aenter():
        if enter_error is not None:
            raise enter_error
        return enter_result

    async def _aexit(*_args):
        return False

    cm.__aenter__ = MagicMock(side_effect=_aenter)
    cm.__aexit__ = MagicMock(side_effect=_aexit)
    return cm


@pytest.mark.asyncio
async def test_setup_default_chain_session_verifies_identity():
    client = AsyncAWSClient(MagicMock(env="test"), "us-east-1")

    sts_client = MagicMock()
    sts_client.get_caller_identity = AsyncMock(
        return_value={"Arn": "arn:aws:sts::123456789012:assumed-role/my-role/i-abc"}
    )
    session = MagicMock()
    session.client.return_value = _sts_client_context(enter_result=sts_client)

    with patch("analytiq_data.aws.aws_client.aioboto3.Session", return_value=session):
        await client._setup_default_chain_session()

    assert client.session is session
    sts_client.get_caller_identity.assert_awaited_once()


@pytest.mark.asyncio
async def test_setup_default_chain_session_raises_troubleshootable_error():
    client = AsyncAWSClient(MagicMock(env="test"), "us-east-1")
    client.session = None  # neutral default normally set by init()

    session = MagicMock()
    session.client.return_value = _sts_client_context(
        enter_error=Exception("Unable to locate credentials")
    )

    with patch("analytiq_data.aws.aws_client.aioboto3.Session", return_value=session):
        with pytest.raises(Exception) as exc_info:
            await client._setup_default_chain_session()

    message = str(exc_info.value)
    assert "cloud_config" in message
    assert "default credential chain" in message
    assert "instance profile" in message
    assert "Unable to locate credentials" in message
    assert client.session is None


@pytest.mark.asyncio
async def test_add_aws_params_omits_empty_static_keys():
    from analytiq_data.llm.llm_aws import add_aws_params

    aws_client = MagicMock(
        aws_access_key_id="",
        aws_secret_access_key="",
        region_name="us-east-1",
    )
    params: dict = {}
    with patch(
        "analytiq_data.aws.get_aws_client_async",
        AsyncMock(return_value=aws_client),
    ):
        await add_aws_params(MagicMock(env="test"), params)

    assert "aws_access_key_id" not in params
    assert "aws_secret_access_key" not in params
    assert params["aws_region_name"] == "us-east-1"


@pytest.mark.asyncio
async def test_add_aws_params_injects_static_keys_when_present():
    from analytiq_data.llm.llm_aws import add_aws_params

    aws_client = MagicMock(
        aws_access_key_id="key",
        aws_secret_access_key="secret",
        region_name="us-east-1",
    )
    params: dict = {}
    with patch(
        "analytiq_data.aws.get_aws_client_async",
        AsyncMock(return_value=aws_client),
    ):
        await add_aws_params(MagicMock(env="test"), params)

    assert params["aws_access_key_id"] == "key"
    assert params["aws_secret_access_key"] == "secret"
    assert params["aws_region_name"] == "us-east-1"
