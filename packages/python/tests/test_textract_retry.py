import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from botocore.exceptions import ClientError

import analytiq_data as ad
from analytiq_data.aws import textract as textract_mod


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

    # Speed up: avoid real sleeps from polling/backoff (and stamina wait)
    async def _no_sleep(_t):
        return None

    monkeypatch.setattr(asyncio, "sleep", _no_sleep)

    aws_client = MagicMock()
    aws_client.s3_bucket_name = "bucket"

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
            throughput_exc,  # first poll attempt throttled
            {"JobStatus": "SUCCEEDED"},  # poll succeeds
            {  # results page
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

    # Ensure retry happened (i.e., we attempted the call again after the exception)
    assert textract_client.get_document_text_detection.await_count >= 2

