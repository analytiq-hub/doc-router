import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from botocore.exceptions import ClientError

import analytiq_data as ad
from analytiq_data.aws import textract as textract_mod
from analytiq_data.aws.aws_client import AsyncAWSClient


@pytest.mark.asyncio
async def test_textract_retries_provisioned_throughput_exceeded(monkeypatch):
    """
    run_textract should retry Textract API calls when botocore raises a ClientError with
    Error.Code == ProvisionedThroughputExceededException.
    """

    class FakeCtx:
        def __init__(self, inner):
            self._inner = inner

        async def __aenter__(self):
            return self._inner

        async def __aexit__(self, exc_type, exc, tb):
            return False

    async def _no_sleep(_t):
        return None

    monkeypatch.setattr(asyncio, "sleep", _no_sleep)

    aws_client = MagicMock()
    aws_client.s3_bucket_name = "bucket"
    aws_client.refresh_credentials = AsyncMock()
    aws_client.is_refreshable_auth_error = AsyncAWSClient.is_refreshable_auth_error

    s3_client = MagicMock()
    s3_client.put_object = AsyncMock(return_value=None)
    s3_client.delete_object = AsyncMock(return_value=None)

    textract_client = MagicMock()
    textract_client.start_document_text_detection = AsyncMock(return_value={"JobId": "job-1"})

    throughput_exc = ClientError(
        error_response={
            "Error": {
                "Code": "ProvisionedThroughputExceededException",
                "Message": "rate exceeded",
            }
        },
        operation_name="GetDocumentTextDetection",
    )

    textract_client.get_document_text_detection = AsyncMock(
        side_effect=[
            throughput_exc,
            {"JobStatus": "SUCCEEDED"},
            {
                "JobStatus": "SUCCEEDED",
                "Blocks": [],
                "DocumentMetadata": {"Pages": 1},
                "DetectDocumentTextModelVersion": "v1",
            },
        ]
    )

    aws_client.client.side_effect = lambda name: FakeCtx(
        s3_client if name == "s3" else textract_client
    )

    monkeypatch.setattr(ad.aws, "get_aws_client_async", AsyncMock(return_value=aws_client))

    out = await textract_mod.run_textract(MagicMock(name="c"), b"blob")

    assert isinstance(out, dict)
    assert out["Blocks"] == []
    assert out["DocumentMetadata"]["Pages"] == 1
    assert textract_client.get_document_text_detection.await_count >= 2


@pytest.mark.asyncio
async def test_textract_retries_expired_token_on_put_object(monkeypatch):
    class FakeCtx:
        def __init__(self, inner):
            self._inner = inner

        async def __aenter__(self):
            return self._inner

        async def __aexit__(self, exc_type, exc, tb):
            return False

    expired_exc = ClientError(
        error_response={
            "Error": {
                "Code": "ExpiredToken",
                "Message": "The provided token has expired.",
            }
        },
        operation_name="PutObject",
    )

    aws_client = MagicMock()
    aws_client.s3_bucket_name = "bucket"
    aws_client.refresh_credentials = AsyncMock()
    aws_client.is_refreshable_auth_error = AsyncAWSClient.is_refreshable_auth_error

    s3_client = MagicMock()
    s3_client.put_object = AsyncMock(side_effect=[expired_exc, None])
    s3_client.delete_object = AsyncMock(return_value=None)

    textract_client = MagicMock()
    textract_client.start_document_text_detection = AsyncMock(return_value={"JobId": "job-1"})
    textract_client.get_document_text_detection = AsyncMock(
        side_effect=[
            {"JobStatus": "SUCCEEDED"},
            {
                "JobStatus": "SUCCEEDED",
                "Blocks": [],
                "DocumentMetadata": {"Pages": 1},
                "DetectDocumentTextModelVersion": "v1",
            },
        ]
    )

    aws_client.client.side_effect = lambda name: FakeCtx(
        s3_client if name == "s3" else textract_client
    )

    monkeypatch.setattr(ad.aws, "get_aws_client_async", AsyncMock(return_value=aws_client))

    out = await textract_mod.run_textract(MagicMock(name="c"), b"blob")

    assert isinstance(out, dict)
    assert out["Blocks"] == []
    assert s3_client.put_object.await_count == 2
    assert aws_client.refresh_credentials.await_count >= 2


@pytest.mark.asyncio
async def test_textract_concurrency_serializes_when_limit_one(monkeypatch):
    monkeypatch.setattr(textract_mod, "TEXTRACT_MAX_CONCURRENT", 1)
    monkeypatch.setattr(textract_mod, "_textract_in_flight", 0)
    monkeypatch.setattr(textract_mod, "_textract_high_waiting", 0)
    monkeypatch.setattr(textract_mod, "_textract_gate", None)

    active = 0
    max_active = 0
    lock = asyncio.Lock()
    first_holding = asyncio.Event()
    release = asyncio.Event()

    async def gated() -> None:
        nonlocal active, max_active
        async with textract_mod._textract_concurrency("high"):
            async with lock:
                active += 1
                max_active = max(max_active, active)
            first_holding.set()
            await release.wait()
            async with lock:
                active -= 1

    first = asyncio.create_task(gated())
    await first_holding.wait()
    second = asyncio.create_task(gated())
    await asyncio.sleep(0)
    async with lock:
        assert active == 1
        assert max_active == 1

    release.set()
    await asyncio.gather(first, second)
    assert max_active == 1


async def _wait_until(predicate, *, timeout: float = 1.0) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while not predicate():
        if loop.time() >= deadline:
            raise TimeoutError(f"condition not met within {timeout}s")
        await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_textract_low_priority_yields_while_high_priority_waiting(monkeypatch):
    monkeypatch.setattr(textract_mod, "TEXTRACT_MAX_CONCURRENT", 1)
    monkeypatch.setattr(textract_mod, "_textract_in_flight", 0)
    monkeypatch.setattr(textract_mod, "_textract_high_waiting", 0)
    monkeypatch.setattr(textract_mod, "_textract_gate", None)

    holder_entered = asyncio.Event()
    low_started = asyncio.Event()
    release_holder = asyncio.Event()
    high_acquired = asyncio.Event()
    release_high = asyncio.Event()

    async def hold_slot():
        async with textract_mod._textract_concurrency("high"):
            holder_entered.set()
            await release_holder.wait()

    async def waiting_high():
        async with textract_mod._textract_concurrency("high"):
            high_acquired.set()
            await release_high.wait()

    async def low_priority():
        await holder_entered.wait()
        async with textract_mod._textract_concurrency("low"):
            low_started.set()

    holder = asyncio.create_task(hold_slot())
    await holder_entered.wait()

    high_task = asyncio.create_task(waiting_high())
    await _wait_until(lambda: textract_mod._textract_high_waiting > 0)

    low_task = asyncio.create_task(low_priority())
    await asyncio.sleep(0)
    assert not low_started.is_set()

    release_holder.set()
    await holder
    await high_acquired.wait()
    assert not low_started.is_set()

    release_high.set()
    await high_task
    await low_task
    assert low_started.is_set()
