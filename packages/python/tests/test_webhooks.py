import os
import logging
import time
import json
import hmac
import hashlib
from datetime import datetime, UTC, timedelta
from unittest.mock import patch, AsyncMock, MagicMock

import pytest
import httpx
from bson import ObjectId

import analytiq_data as ad
from analytiq_data.webhooks.dispatch import (
    _webhook_enabled_for_event,
    _compute_signature,
    _compute_backoff,
    _is_retryable_status,
    _json_dumps_compact,
    _decrypt_secret_if_needed,
    _decrypt_token_if_needed,
    generate_webhook_secret,
    DELIVERIES_COLLECTION,
)
from analytiq_data.msg_handlers.webhook import process_webhook_msg

# Import shared test utilities
from .conftest_utils import client, TEST_ORG_ID, get_auth_headers

logger = logging.getLogger(__name__)

# Check that ENV is set to pytest
assert os.environ["ENV"] == "pytest"


@pytest.mark.asyncio
async def test_webhook_config_update_all_options(test_db, mock_auth):
    logger.info("test_webhook_config_update_all_options() start")

    payload = {
        "enabled": True,
        "url": "https://example.com/webhook",
        "events": ["document.uploaded", "llm.completed", "llm.error", "webhook.test"],
        "auth_type": "header",
        "auth_header_name": "X-Api-Key",
        "auth_header_value": "supersecret",
    }

    response = client.put(
        f"/v0/orgs/{TEST_ORG_ID}/webhook",
        json=payload,
        headers=get_auth_headers(),
    )
    assert response.status_code == 200, response.json()
    data = response.json()

    assert data["enabled"] is True
    assert data["url"] == payload["url"]
    assert data["events"] == payload["events"]
    assert data["auth_type"] == "header"
    assert data["auth_header_name"] == "X-Api-Key"
    assert data["auth_header_set"] is True
    assert data["auth_header_preview"] == f"{payload['auth_header_value'][:5]}..."

    secret_payload = {"secret": "whs_test_secret_value"}
    secret_response = client.put(
        f"/v0/orgs/{TEST_ORG_ID}/webhook",
        json=secret_payload,
        headers=get_auth_headers(),
    )
    assert secret_response.status_code == 200, secret_response.json()
    secret_data = secret_response.json()
    assert secret_data["secret_set"] is True
    assert secret_data["secret_preview"] == f"{secret_payload['secret'][:16]}..."

    get_response = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/webhook",
        headers=get_auth_headers(),
    )
    assert get_response.status_code == 200, get_response.json()
    get_data = get_response.json()
    assert get_data["enabled"] is True
    assert get_data["url"] == payload["url"]
    assert get_data["events"] == payload["events"]
    assert get_data["auth_type"] == "header"
    assert get_data["auth_header_name"] == "X-Api-Key"
    assert get_data["secret_set"] is True
    assert get_data["auth_header_set"] is True

    org = await test_db.organizations.find_one({"_id": ObjectId(TEST_ORG_ID)})
    assert org is not None
    cfg = org.get("webhook") or {}
    assert cfg.get("auth_type") == "header"
    assert cfg.get("signature_enabled") is False

    logger.info("test_webhook_config_update_all_options() end")


@pytest.mark.asyncio
async def test_webhook_config_clear_and_regenerate(test_db, mock_auth):
    logger.info("test_webhook_config_clear_and_regenerate() start")

    regen_secret = "whs_regenerated_secret_value"
    with patch("analytiq_data.webhooks.generate_webhook_secret", return_value=regen_secret):
        payload = {
            "auth_type": "hmac",
            "auth_header_name": "   ",
            "auth_header_value": "",
            "secret": "",
        }
        response = client.put(
            f"/v0/orgs/{TEST_ORG_ID}/webhook",
            json=payload,
            headers=get_auth_headers(),
        )

    assert response.status_code == 200
    data = response.json()
    assert data["auth_type"] == "hmac"
    assert data["auth_header_name"] is None
    assert data["auth_header_set"] is False
    assert data["auth_header_preview"] is None
    assert data["generated_secret"] == regen_secret
    assert data["secret_set"] is True
    assert data["secret_preview"] == f"{regen_secret[:16]}..."

    org = await test_db.organizations.find_one({"_id": ObjectId(TEST_ORG_ID)})
    assert org is not None
    cfg = org.get("webhook") or {}
    assert cfg.get("auth_type") == "hmac"
    assert cfg.get("signature_enabled") is True
    assert cfg.get("auth_header_name") is None
    assert cfg.get("auth_header_value") is None

    logger.info("test_webhook_config_clear_and_regenerate() end")


def test_webhook_enabled_for_all_triggers():
    cfg_all = {"enabled": True, "url": "https://example.com/webhook", "events": None}
    triggers = [
        "document.uploaded",
        "document.error",
        "llm.completed",
        "llm.error",
        "webhook.test",
    ]
    for event_type in triggers:
        assert _webhook_enabled_for_event(cfg_all, event_type) is True

    cfg_limited = {"enabled": True, "url": "https://example.com/webhook", "events": ["document.uploaded"]}
    assert _webhook_enabled_for_event(cfg_limited, "document.uploaded") is True
    assert _webhook_enabled_for_event(cfg_limited, "llm.completed") is False
    assert _webhook_enabled_for_event(cfg_limited, "webhook.test") is True

    cfg_disabled = {"enabled": False, "url": "https://example.com/webhook", "events": None}
    assert _webhook_enabled_for_event(cfg_disabled, "document.uploaded") is False


@pytest.mark.asyncio
async def test_send_delivery_retries_on_exception():
    logger.info("test_send_delivery_retries_on_exception() start")

    class FailingAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *args, **kwargs):
            raise RuntimeError("boom")

    delivery = {
        "_id": ObjectId(),
        "event_type": "document.error",
        "event_id": "evt_123",
        "target_url": "https://example.com/webhook",
        "auth_type": "hmac",
        "secret_encrypted": "not_encrypted",
    }

    analytiq_client = object()
    with patch("analytiq_data.webhooks.dispatch.httpx.AsyncClient", FailingAsyncClient):
        with patch("analytiq_data.webhooks.dispatch.mark_retry", new_callable=AsyncMock) as mock_retry:
            await ad.webhooks.send_delivery(analytiq_client, delivery)

    assert mock_retry.called is True
    args, kwargs = mock_retry.call_args
    assert args[0] is analytiq_client
    assert args[1] == delivery
    assert "exception: RuntimeError: boom" in kwargs["error"]

    logger.info("test_send_delivery_retries_on_exception() end")


# ============================================================================
# Utility Function Tests
# ============================================================================


def test_generate_webhook_secret():
    """Test webhook secret generation format"""
    secret = generate_webhook_secret()
    assert secret.startswith("whs_")
    assert len(secret) > 20  # Prefix + base64 encoded bytes


def test_compute_signature():
    """Test HMAC-SHA256 signature computation"""
    secret = "test_secret"
    ts = 1234567890
    body = '{"event":"test"}'

    signature = _compute_signature(secret, ts, body)

    assert signature.startswith("sha256=")
    # Verify the signature manually
    expected_msg = f"{ts}.{body}".encode("utf-8")
    expected_mac = hmac.new(secret.encode("utf-8"), expected_msg, hashlib.sha256).hexdigest()
    assert signature == f"sha256={expected_mac}"


def test_compute_signature_with_unicode():
    """Test signature computation with unicode characters"""
    secret = "test_secret"
    ts = 1234567890
    body = '{"name":"테스트"}'  # Korean text

    signature = _compute_signature(secret, ts, body)
    assert signature.startswith("sha256=")


def test_json_dumps_compact():
    """Test compact JSON serialization"""
    payload = {"key": "value", "number": 123, "nested": {"a": 1}}
    result = _json_dumps_compact(payload)

    # No extra spaces
    assert " " not in result or result.count(" ") == 0
    # Valid JSON
    parsed = json.loads(result)
    assert parsed == payload


def test_is_retryable_status():
    """Test HTTP status code classification for retries"""
    # Retryable statuses
    assert _is_retryable_status(408) is True  # Request Timeout
    assert _is_retryable_status(429) is True  # Too Many Requests
    assert _is_retryable_status(500) is True  # Internal Server Error
    assert _is_retryable_status(502) is True  # Bad Gateway
    assert _is_retryable_status(503) is True  # Service Unavailable
    assert _is_retryable_status(504) is True  # Gateway Timeout
    assert _is_retryable_status(599) is True  # Edge of 5xx range

    # Non-retryable statuses
    assert _is_retryable_status(200) is False  # OK
    assert _is_retryable_status(201) is False  # Created
    assert _is_retryable_status(400) is False  # Bad Request
    assert _is_retryable_status(401) is False  # Unauthorized
    assert _is_retryable_status(403) is False  # Forbidden
    assert _is_retryable_status(404) is False  # Not Found
    assert _is_retryable_status(422) is False  # Unprocessable Entity


def test_compute_backoff():
    """Test exponential backoff calculation"""
    # First attempt should use base delay
    with patch.dict(os.environ, {
        "WEBHOOK_BACKOFF_BASE_SECS": "5.0",
        "WEBHOOK_BACKOFF_CAP_SECS": "900.0",
        "WEBHOOK_BACKOFF_JITTER_SECS": "0.0",  # Disable jitter for predictable tests
    }):
        backoff1 = _compute_backoff(1)
        assert 4.9 <= backoff1.total_seconds() <= 5.1  # ~5 seconds

        # Second attempt should double
        backoff2 = _compute_backoff(2)
        assert 9.9 <= backoff2.total_seconds() <= 10.1  # ~10 seconds

        # Third attempt
        backoff3 = _compute_backoff(3)
        assert 19.9 <= backoff3.total_seconds() <= 20.1  # ~20 seconds


def test_compute_backoff_cap():
    """Test backoff is capped at maximum"""
    with patch.dict(os.environ, {
        "WEBHOOK_BACKOFF_BASE_SECS": "5.0",
        "WEBHOOK_BACKOFF_CAP_SECS": "60.0",  # Low cap for testing
        "WEBHOOK_BACKOFF_JITTER_SECS": "0.0",
    }):
        # High attempt count should hit the cap
        backoff = _compute_backoff(10)
        assert backoff.total_seconds() <= 60.1


def test_compute_backoff_with_jitter():
    """Test backoff includes jitter"""
    with patch.dict(os.environ, {
        "WEBHOOK_BACKOFF_BASE_SECS": "5.0",
        "WEBHOOK_BACKOFF_CAP_SECS": "900.0",
        "WEBHOOK_BACKOFF_JITTER_SECS": "2.0",
    }):
        backoff = _compute_backoff(1)
        # Should be between 5 and 7 seconds (base + up to jitter)
        assert 5.0 <= backoff.total_seconds() <= 7.1


def test_decrypt_secret_if_needed_with_none():
    """Test decryption returns None for None input"""
    assert _decrypt_secret_if_needed(None) is None


def test_decrypt_secret_if_needed_with_plaintext():
    """Test decryption returns plaintext if decryption fails"""
    # If it can't decrypt (not encrypted), it returns the value as-is
    result = _decrypt_secret_if_needed("plaintext_secret")
    assert result == "plaintext_secret"


def test_decrypt_token_if_needed_with_none():
    """Test token decryption returns None for None input"""
    assert _decrypt_token_if_needed(None) is None


def test_decrypt_token_if_needed_with_plaintext():
    """Test token decryption returns plaintext if decryption fails"""
    result = _decrypt_token_if_needed("plaintext_token")
    assert result == "plaintext_token"


# ============================================================================
# HTTP Response Handling Tests
# ============================================================================


@pytest.mark.asyncio
async def test_send_delivery_success_2xx():
    """Test successful delivery with 2xx response"""
    logger.info("test_send_delivery_success_2xx() start")

    class SuccessAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *args, **kwargs):
            resp = MagicMock()
            resp.status_code = 200
            resp.content = b'{"status":"ok"}'
            resp.text = '{"status":"ok"}'
            return resp

    delivery = {
        "_id": ObjectId(),
        "event_type": "document.uploaded",
        "event_id": "evt_123",
        "target_url": "https://example.com/webhook",
        "auth_type": "hmac",
        "secret_encrypted": "test_secret",
        "payload": {"event_id": "evt_123"},
    }

    analytiq_client = object()
    with patch("analytiq_data.webhooks.dispatch.httpx.AsyncClient", SuccessAsyncClient):
        with patch("analytiq_data.webhooks.dispatch.mark_delivered", new_callable=AsyncMock) as mock_delivered:
            await ad.webhooks.send_delivery(analytiq_client, delivery)

    assert mock_delivered.called is True
    args, kwargs = mock_delivered.call_args
    assert args[0] is analytiq_client
    assert args[1] == str(delivery["_id"])
    assert kwargs["http_status"] == 200

    logger.info("test_send_delivery_success_2xx() end")


@pytest.mark.asyncio
async def test_send_delivery_retryable_5xx():
    """Test delivery retry on 5xx response"""
    logger.info("test_send_delivery_retryable_5xx() start")

    class ServerErrorAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *args, **kwargs):
            resp = MagicMock()
            resp.status_code = 503
            resp.content = b"Service Unavailable"
            resp.text = "Service Unavailable"
            return resp

    delivery = {
        "_id": ObjectId(),
        "event_type": "document.uploaded",
        "event_id": "evt_123",
        "target_url": "https://example.com/webhook",
        "auth_type": "hmac",
        "secret_encrypted": "test_secret",
        "payload": {"event_id": "evt_123"},
        "attempts": 1,
        "max_attempts": 10,
    }

    analytiq_client = object()
    with patch("analytiq_data.webhooks.dispatch.httpx.AsyncClient", ServerErrorAsyncClient):
        with patch("analytiq_data.webhooks.dispatch.mark_retry", new_callable=AsyncMock) as mock_retry:
            await ad.webhooks.send_delivery(analytiq_client, delivery)

    assert mock_retry.called is True
    args, kwargs = mock_retry.call_args
    assert args[1] == delivery
    assert kwargs["http_status"] == 503
    assert "http_503" in kwargs["error"]

    logger.info("test_send_delivery_retryable_5xx() end")


@pytest.mark.asyncio
async def test_send_delivery_non_retryable_4xx():
    """Test delivery failure on non-retryable 4xx response"""
    logger.info("test_send_delivery_non_retryable_4xx() start")

    class BadRequestAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *args, **kwargs):
            resp = MagicMock()
            resp.status_code = 400
            resp.content = b"Bad Request"
            resp.text = "Bad Request"
            return resp

    delivery = {
        "_id": ObjectId(),
        "event_type": "document.uploaded",
        "event_id": "evt_123",
        "target_url": "https://example.com/webhook",
        "auth_type": "hmac",
        "secret_encrypted": "test_secret",
        "payload": {"event_id": "evt_123"},
    }

    analytiq_client = object()
    with patch("analytiq_data.webhooks.dispatch.httpx.AsyncClient", BadRequestAsyncClient):
        with patch("analytiq_data.webhooks.dispatch.mark_failed", new_callable=AsyncMock) as mock_failed:
            await ad.webhooks.send_delivery(analytiq_client, delivery)

    assert mock_failed.called is True
    args, kwargs = mock_failed.call_args
    assert args[1] == str(delivery["_id"])
    assert kwargs["http_status"] == 400
    assert "http_400" in kwargs["error"]

    logger.info("test_send_delivery_non_retryable_4xx() end")


@pytest.mark.asyncio
async def test_send_delivery_retryable_429():
    """Test delivery retry on 429 Too Many Requests"""
    logger.info("test_send_delivery_retryable_429() start")

    class RateLimitAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *args, **kwargs):
            resp = MagicMock()
            resp.status_code = 429
            resp.content = b"Too Many Requests"
            resp.text = "Too Many Requests"
            return resp

    delivery = {
        "_id": ObjectId(),
        "event_type": "document.uploaded",
        "event_id": "evt_123",
        "target_url": "https://example.com/webhook",
        "auth_type": "hmac",
        "secret_encrypted": "test_secret",
        "payload": {"event_id": "evt_123"},
        "attempts": 1,
        "max_attempts": 10,
    }

    analytiq_client = object()
    with patch("analytiq_data.webhooks.dispatch.httpx.AsyncClient", RateLimitAsyncClient):
        with patch("analytiq_data.webhooks.dispatch.mark_retry", new_callable=AsyncMock) as mock_retry:
            await ad.webhooks.send_delivery(analytiq_client, delivery)

    assert mock_retry.called is True
    kwargs = mock_retry.call_args[1]
    assert kwargs["http_status"] == 429

    logger.info("test_send_delivery_retryable_429() end")


@pytest.mark.asyncio
async def test_send_delivery_with_header_auth():
    """Test delivery sends custom auth header when auth_type is header"""
    logger.info("test_send_delivery_with_header_auth() start")

    captured_headers = {}

    class CaptureHeadersAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, content, headers):
            nonlocal captured_headers
            captured_headers = headers
            resp = MagicMock()
            resp.status_code = 200
            resp.content = b'{"ok":true}'
            resp.text = '{"ok":true}'
            return resp

    delivery = {
        "_id": ObjectId(),
        "event_type": "document.uploaded",
        "event_id": "evt_123",
        "target_url": "https://example.com/webhook",
        "auth_type": "header",
        "auth_header_name": "X-Api-Key",
        "auth_header_value": "my_api_key",
        "payload": {"event_id": "evt_123"},
    }

    analytiq_client = object()
    with patch("analytiq_data.webhooks.dispatch.httpx.AsyncClient", CaptureHeadersAsyncClient):
        with patch("analytiq_data.webhooks.dispatch.mark_delivered", new_callable=AsyncMock):
            await ad.webhooks.send_delivery(analytiq_client, delivery)

    assert "X-Api-Key" in captured_headers
    assert captured_headers["X-Api-Key"] == "my_api_key"
    # Should NOT have signature header when auth_type is header
    assert "X-DocRouter-Signature" not in captured_headers or captured_headers.get("X-DocRouter-Signature") is None

    logger.info("test_send_delivery_with_header_auth() end")


@pytest.mark.asyncio
async def test_send_delivery_with_hmac_signature():
    """Test delivery sends HMAC signature when auth_type is hmac"""
    logger.info("test_send_delivery_with_hmac_signature() start")

    captured_headers = {}

    class CaptureHeadersAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, content, headers):
            nonlocal captured_headers
            captured_headers = headers
            resp = MagicMock()
            resp.status_code = 200
            resp.content = b'{"ok":true}'
            resp.text = '{"ok":true}'
            return resp

    delivery = {
        "_id": ObjectId(),
        "event_type": "document.uploaded",
        "event_id": "evt_123",
        "target_url": "https://example.com/webhook",
        "auth_type": "hmac",
        "secret_encrypted": "my_webhook_secret",
        "payload": {"event_id": "evt_123"},
    }

    analytiq_client = object()
    with patch("analytiq_data.webhooks.dispatch.httpx.AsyncClient", CaptureHeadersAsyncClient):
        with patch("analytiq_data.webhooks.dispatch.mark_delivered", new_callable=AsyncMock):
            await ad.webhooks.send_delivery(analytiq_client, delivery)

    assert "X-DocRouter-Signature" in captured_headers
    assert captured_headers["X-DocRouter-Signature"].startswith("sha256=")
    assert "X-DocRouter-Event" in captured_headers
    assert captured_headers["X-DocRouter-Event"] == "document.uploaded"
    assert "X-DocRouter-Event-Id" in captured_headers
    assert "X-DocRouter-Timestamp" in captured_headers

    logger.info("test_send_delivery_with_hmac_signature() end")


# ============================================================================
# Delivery State Transition Tests
# ============================================================================


@pytest.mark.asyncio
async def test_mark_delivered(test_db, mock_auth):
    """Test marking a delivery as delivered"""
    logger.info("test_mark_delivered() start")

    # Insert a test delivery
    delivery_id = ObjectId()
    await test_db[DELIVERIES_COLLECTION].insert_one({
        "_id": delivery_id,
        "event_id": "evt_test",
        "event_type": "webhook.test",
        "organization_id": TEST_ORG_ID,
        "status": "processing",
        "attempts": 1,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    })

    analytiq_client = MagicMock()
    analytiq_client.async_db = test_db

    with patch("analytiq_data.common.get_async_db", return_value=test_db):
        await ad.webhooks.mark_delivered(
            analytiq_client,
            str(delivery_id),
            http_status=200,
            response_text='{"ok":true}',
        )

    # Verify the delivery was updated
    delivery = await test_db[DELIVERIES_COLLECTION].find_one({"_id": delivery_id})
    assert delivery["status"] == "delivered"
    assert delivery["last_http_status"] == 200
    assert delivery["last_response_text"] == '{"ok":true}'
    assert delivery["delivered_at"] is not None

    logger.info("test_mark_delivered() end")


@pytest.mark.asyncio
async def test_mark_failed(test_db, mock_auth):
    """Test marking a delivery as failed"""
    logger.info("test_mark_failed() start")

    delivery_id = ObjectId()
    await test_db[DELIVERIES_COLLECTION].insert_one({
        "_id": delivery_id,
        "event_id": "evt_test",
        "event_type": "webhook.test",
        "organization_id": TEST_ORG_ID,
        "status": "processing",
        "attempts": 10,
        "max_attempts": 10,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    })

    analytiq_client = MagicMock()

    with patch("analytiq_data.common.get_async_db", return_value=test_db):
        await ad.webhooks.mark_failed(
            analytiq_client,
            str(delivery_id),
            http_status=400,
            error="http_400",
            response_text="Bad Request",
        )

    delivery = await test_db[DELIVERIES_COLLECTION].find_one({"_id": delivery_id})
    assert delivery["status"] == "failed"
    assert delivery["last_http_status"] == 400
    assert delivery["last_error"] == "http_400"
    assert delivery["failed_at"] is not None

    logger.info("test_mark_failed() end")


@pytest.mark.asyncio
async def test_mark_retry_schedules_next_attempt(test_db, mock_auth):
    """Test mark_retry schedules the next attempt with backoff"""
    logger.info("test_mark_retry_schedules_next_attempt() start")

    delivery_id = ObjectId()
    delivery = {
        "_id": delivery_id,
        "event_id": "evt_test",
        "event_type": "webhook.test",
        "organization_id": TEST_ORG_ID,
        "status": "processing",
        "attempts": 2,
        "max_attempts": 10,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    await test_db[DELIVERIES_COLLECTION].insert_one(delivery)

    analytiq_client = MagicMock()

    with patch("analytiq_data.common.get_async_db", return_value=test_db):
        await ad.webhooks.mark_retry(
            analytiq_client,
            delivery,
            http_status=503,
            error="http_503",
            response_text="Service Unavailable",
        )

    updated = await test_db[DELIVERIES_COLLECTION].find_one({"_id": delivery_id})
    assert updated["status"] == "pending"
    assert updated["last_http_status"] == 503
    assert updated["next_attempt_at"] is not None
    # Next attempt should be in the future (compare with timezone-naive for MongoDB compatibility)
    now_naive = datetime.now(UTC).replace(tzinfo=None)
    next_attempt_naive = updated["next_attempt_at"].replace(tzinfo=None) if updated["next_attempt_at"].tzinfo else updated["next_attempt_at"]
    assert next_attempt_naive > now_naive

    logger.info("test_mark_retry_schedules_next_attempt() end")


@pytest.mark.asyncio
async def test_mark_retry_fails_after_max_attempts(test_db, mock_auth):
    """Test mark_retry marks as failed when max attempts reached"""
    logger.info("test_mark_retry_fails_after_max_attempts() start")

    delivery_id = ObjectId()
    delivery = {
        "_id": delivery_id,
        "event_id": "evt_test",
        "event_type": "webhook.test",
        "organization_id": TEST_ORG_ID,
        "status": "processing",
        "attempts": 10,
        "max_attempts": 10,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    await test_db[DELIVERIES_COLLECTION].insert_one(delivery)

    analytiq_client = MagicMock()

    with patch("analytiq_data.common.get_async_db", return_value=test_db):
        await ad.webhooks.mark_retry(
            analytiq_client,
            delivery,
            http_status=503,
            error="http_503",
            response_text="Service Unavailable",
        )

    updated = await test_db[DELIVERIES_COLLECTION].find_one({"_id": delivery_id})
    assert updated["status"] == "failed"
    assert "max_attempts_exceeded" in updated["last_error"]

    logger.info("test_mark_retry_fails_after_max_attempts() end")


# ============================================================================
# Enqueue Event and Delivery Claiming Tests
# ============================================================================


@pytest.mark.asyncio
async def test_enqueue_event_creates_delivery(test_db, mock_auth):
    """Test enqueue_event creates a delivery record and sends queue message"""
    logger.info("test_enqueue_event_creates_delivery() start")

    # Set up webhook config for the organization
    await test_db.organizations.update_one(
        {"_id": ObjectId(TEST_ORG_ID)},
        {"$set": {
            "webhook": {
                "enabled": True,
                "url": "https://example.com/webhook",
                "events": None,
                "auth_type": "hmac",
                "secret": "encrypted_secret",
            }
        }}
    )

    analytiq_client = MagicMock()

    with patch("analytiq_data.common.get_async_db", return_value=test_db):
        with patch("analytiq_data.queue.send_msg", new_callable=AsyncMock) as mock_send:
            delivery_id = await ad.webhooks.enqueue_event(
                analytiq_client,
                organization_id=TEST_ORG_ID,
                event_type="webhook.test",
                document_id=None,
            )

    assert delivery_id is not None
    assert mock_send.called is True

    # Verify delivery was created
    delivery = await test_db[DELIVERIES_COLLECTION].find_one({"_id": ObjectId(delivery_id)})
    assert delivery is not None
    assert delivery["event_type"] == "webhook.test"
    assert delivery["organization_id"] == TEST_ORG_ID
    assert delivery["status"] == "pending"
    assert delivery["target_url"] == "https://example.com/webhook"

    logger.info("test_enqueue_event_creates_delivery() end")


@pytest.mark.asyncio
async def test_enqueue_event_returns_none_when_disabled(test_db, mock_auth):
    """Test enqueue_event returns None when webhook is disabled"""
    logger.info("test_enqueue_event_returns_none_when_disabled() start")

    # Set up disabled webhook config
    await test_db.organizations.update_one(
        {"_id": ObjectId(TEST_ORG_ID)},
        {"$set": {
            "webhook": {
                "enabled": False,
                "url": "https://example.com/webhook",
            }
        }}
    )

    analytiq_client = MagicMock()

    with patch("analytiq_data.common.get_async_db", return_value=test_db):
        delivery_id = await ad.webhooks.enqueue_event(
            analytiq_client,
            organization_id=TEST_ORG_ID,
            event_type="document.uploaded",
            document_id=None,
        )

    assert delivery_id is None

    logger.info("test_enqueue_event_returns_none_when_disabled() end")


@pytest.mark.asyncio
async def test_enqueue_event_filters_by_event_type(test_db, mock_auth):
    """Test enqueue_event respects event type filter"""
    logger.info("test_enqueue_event_filters_by_event_type() start")

    # Set up webhook config with limited events
    await test_db.organizations.update_one(
        {"_id": ObjectId(TEST_ORG_ID)},
        {"$set": {
            "webhook": {
                "enabled": True,
                "url": "https://example.com/webhook",
                "events": ["document.uploaded"],  # Only document.uploaded
            }
        }}
    )

    analytiq_client = MagicMock()

    with patch("analytiq_data.common.get_async_db", return_value=test_db):
        # This should be filtered out
        delivery_id = await ad.webhooks.enqueue_event(
            analytiq_client,
            organization_id=TEST_ORG_ID,
            event_type="llm.completed",
            document_id=None,
        )

    assert delivery_id is None

    logger.info("test_enqueue_event_filters_by_event_type() end")


@pytest.mark.asyncio
async def test_claim_delivery_by_id(test_db, mock_auth):
    """Test claiming a specific delivery by ID"""
    logger.info("test_claim_delivery_by_id() start")

    delivery_id = ObjectId()
    now = datetime.now(UTC)
    await test_db[DELIVERIES_COLLECTION].insert_one({
        "_id": delivery_id,
        "event_id": "evt_test",
        "event_type": "webhook.test",
        "organization_id": TEST_ORG_ID,
        "status": "pending",
        "attempts": 0,
        "next_attempt_at": now - timedelta(seconds=1),  # Due in the past
        "created_at": now,
        "updated_at": now,
    })

    analytiq_client = MagicMock()

    with patch("analytiq_data.common.get_async_db", return_value=test_db):
        claimed = await ad.webhooks.claim_delivery_by_id(analytiq_client, str(delivery_id))

    assert claimed is not None
    assert claimed["status"] == "processing"
    assert claimed["attempts"] == 1

    logger.info("test_claim_delivery_by_id() end")


@pytest.mark.asyncio
async def test_claim_delivery_by_id_not_due(test_db, mock_auth):
    """Test claiming a delivery that's not yet due returns None"""
    logger.info("test_claim_delivery_by_id_not_due() start")

    delivery_id = ObjectId()
    now = datetime.now(UTC)
    await test_db[DELIVERIES_COLLECTION].insert_one({
        "_id": delivery_id,
        "event_id": "evt_test",
        "event_type": "webhook.test",
        "organization_id": TEST_ORG_ID,
        "status": "pending",
        "attempts": 0,
        "next_attempt_at": now + timedelta(hours=1),  # Due in the future
        "created_at": now,
        "updated_at": now,
    })

    analytiq_client = MagicMock()

    with patch("analytiq_data.common.get_async_db", return_value=test_db):
        claimed = await ad.webhooks.claim_delivery_by_id(analytiq_client, str(delivery_id))

    assert claimed is None

    logger.info("test_claim_delivery_by_id_not_due() end")


@pytest.mark.asyncio
async def test_claim_next_due_delivery(test_db, mock_auth):
    """Test claiming the next due delivery"""
    logger.info("test_claim_next_due_delivery() start")

    now = datetime.now(UTC)

    # Insert two deliveries, one due earlier
    delivery1_id = ObjectId()
    delivery2_id = ObjectId()

    await test_db[DELIVERIES_COLLECTION].insert_many([
        {
            "_id": delivery1_id,
            "event_id": "evt_1",
            "event_type": "webhook.test",
            "organization_id": TEST_ORG_ID,
            "status": "pending",
            "attempts": 0,
            "next_attempt_at": now - timedelta(minutes=5),  # Due 5 min ago
            "created_at": now - timedelta(minutes=10),
            "updated_at": now,
        },
        {
            "_id": delivery2_id,
            "event_id": "evt_2",
            "event_type": "webhook.test",
            "organization_id": TEST_ORG_ID,
            "status": "pending",
            "attempts": 0,
            "next_attempt_at": now - timedelta(minutes=1),  # Due 1 min ago
            "created_at": now - timedelta(minutes=5),
            "updated_at": now,
        },
    ])

    analytiq_client = MagicMock()

    with patch("analytiq_data.common.get_async_db", return_value=test_db):
        claimed = await ad.webhooks.claim_next_due_delivery(analytiq_client)

    # Should claim the earliest due delivery
    assert claimed is not None
    assert claimed["_id"] == delivery1_id
    assert claimed["status"] == "processing"

    logger.info("test_claim_next_due_delivery() end")


# ============================================================================
# API Endpoint Tests
# ============================================================================


@pytest.mark.asyncio
async def test_webhook_test_endpoint(test_db, mock_auth):
    """Test POST /webhook/test endpoint"""
    logger.info("test_webhook_test_endpoint() start")

    # Set up webhook config
    await test_db.organizations.update_one(
        {"_id": ObjectId(TEST_ORG_ID)},
        {"$set": {
            "webhook": {
                "enabled": True,
                "url": "https://example.com/webhook",
                "events": None,
                "auth_type": "hmac",
            }
        }}
    )

    with patch("analytiq_data.queue.send_msg", new_callable=AsyncMock):
        response = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/webhook/test",
            headers=get_auth_headers(),
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "enqueued"
    assert data["delivery_id"] is not None

    logger.info("test_webhook_test_endpoint() end")


@pytest.mark.asyncio
async def test_webhook_test_endpoint_not_configured(test_db, mock_auth):
    """Test POST /webhook/test returns 400 when not configured"""
    logger.info("test_webhook_test_endpoint_not_configured() start")

    # Ensure webhook is disabled
    await test_db.organizations.update_one(
        {"_id": ObjectId(TEST_ORG_ID)},
        {"$set": {
            "webhook": {
                "enabled": False,
            }
        }}
    )

    response = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/webhook/test",
        headers=get_auth_headers(),
    )

    assert response.status_code == 400
    assert "not enabled" in response.json()["detail"]

    logger.info("test_webhook_test_endpoint_not_configured() end")


@pytest.mark.asyncio
async def test_list_webhook_deliveries(test_db, mock_auth):
    """Test GET /webhook/deliveries endpoint"""
    logger.info("test_list_webhook_deliveries() start")

    now = datetime.now(UTC)

    # Insert test deliveries
    await test_db[DELIVERIES_COLLECTION].insert_many([
        {
            "_id": ObjectId(),
            "event_id": "evt_1",
            "event_type": "document.uploaded",
            "organization_id": TEST_ORG_ID,
            "status": "delivered",
            "attempts": 1,
            "max_attempts": 10,
            "created_at": now - timedelta(hours=1),
            "updated_at": now,
        },
        {
            "_id": ObjectId(),
            "event_id": "evt_2",
            "event_type": "llm.completed",
            "organization_id": TEST_ORG_ID,
            "status": "failed",
            "attempts": 10,
            "max_attempts": 10,
            "created_at": now,
            "updated_at": now,
        },
    ])

    response = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/webhook/deliveries",
        headers=get_auth_headers(),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total_count"] == 2
    assert len(data["deliveries"]) == 2
    # Should be sorted by created_at descending
    assert data["deliveries"][0]["event_id"] == "evt_2"
    assert data["deliveries"][1]["event_id"] == "evt_1"

    logger.info("test_list_webhook_deliveries() end")


@pytest.mark.asyncio
async def test_list_webhook_deliveries_with_filters(test_db, mock_auth):
    """Test GET /webhook/deliveries with status and event_type filters"""
    logger.info("test_list_webhook_deliveries_with_filters() start")

    now = datetime.now(UTC)

    await test_db[DELIVERIES_COLLECTION].insert_many([
        {
            "_id": ObjectId(),
            "event_id": "evt_1",
            "event_type": "document.uploaded",
            "organization_id": TEST_ORG_ID,
            "status": "delivered",
            "attempts": 1,
            "max_attempts": 10,
            "created_at": now,
            "updated_at": now,
        },
        {
            "_id": ObjectId(),
            "event_id": "evt_2",
            "event_type": "llm.completed",
            "organization_id": TEST_ORG_ID,
            "status": "failed",
            "attempts": 10,
            "max_attempts": 10,
            "created_at": now,
            "updated_at": now,
        },
        {
            "_id": ObjectId(),
            "event_id": "evt_3",
            "event_type": "document.uploaded",
            "organization_id": TEST_ORG_ID,
            "status": "failed",
            "attempts": 10,
            "max_attempts": 10,
            "created_at": now,
            "updated_at": now,
        },
    ])

    # Filter by status
    response = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/webhook/deliveries?status=failed",
        headers=get_auth_headers(),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_count"] == 2
    assert all(d["status"] == "failed" for d in data["deliveries"])

    # Filter by event_type
    response = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/webhook/deliveries?event_type=document.uploaded",
        headers=get_auth_headers(),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_count"] == 2
    assert all(d["event_type"] == "document.uploaded" for d in data["deliveries"])

    logger.info("test_list_webhook_deliveries_with_filters() end")


@pytest.mark.asyncio
async def test_list_webhook_deliveries_pagination(test_db, mock_auth):
    """Test GET /webhook/deliveries pagination"""
    logger.info("test_list_webhook_deliveries_pagination() start")

    now = datetime.now(UTC)

    # Insert 5 deliveries
    for i in range(5):
        await test_db[DELIVERIES_COLLECTION].insert_one({
            "_id": ObjectId(),
            "event_id": f"evt_{i}",
            "event_type": "webhook.test",
            "organization_id": TEST_ORG_ID,
            "status": "delivered",
            "attempts": 1,
            "max_attempts": 10,
            "created_at": now + timedelta(minutes=i),
            "updated_at": now,
        })

    # Get first page
    response = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/webhook/deliveries?skip=0&limit=2",
        headers=get_auth_headers(),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_count"] == 5
    assert len(data["deliveries"]) == 2
    assert data["skip"] == 0

    # Get second page
    response = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/webhook/deliveries?skip=2&limit=2",
        headers=get_auth_headers(),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_count"] == 5
    assert len(data["deliveries"]) == 2
    assert data["skip"] == 2

    logger.info("test_list_webhook_deliveries_pagination() end")


@pytest.mark.asyncio
async def test_get_webhook_delivery_details(test_db, mock_auth):
    """Test GET /webhook/deliveries/{delivery_id} endpoint"""
    logger.info("test_get_webhook_delivery_details() start")

    delivery_id = ObjectId()
    now = datetime.now(UTC)
    
    # Encrypt auth_header_value for the test
    test_auth_value = "test_auth_header_value"
    encrypted_auth_value = ad.crypto.encrypt_token(test_auth_value)

    await test_db[DELIVERIES_COLLECTION].insert_one({
        "_id": delivery_id,
        "event_id": "evt_detail",
        "event_type": "document.uploaded",
        "organization_id": TEST_ORG_ID,
        "document_id": "doc_123",
        "status": "delivered",
        "attempts": 1,
        "max_attempts": 10,
        "payload": {"event_id": "evt_detail", "test": True},
        "target_url": "https://example.com/webhook",
        "secret_encrypted": "should_not_be_returned",
        "auth_header_value": encrypted_auth_value,
        "last_http_status": 200,
        "created_at": now,
        "updated_at": now,
    })

    response = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/webhook/deliveries/{delivery_id}",
        headers=get_auth_headers(),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(delivery_id)
    assert data["event_id"] == "evt_detail"
    assert data["payload"]["test"] is True
    # Secret should be removed
    assert "secret_encrypted" not in data

    logger.info("test_get_webhook_delivery_details() end")


@pytest.mark.asyncio
async def test_get_webhook_delivery_not_found(test_db, mock_auth):
    """Test GET /webhook/deliveries/{delivery_id} returns 404 for non-existent"""
    logger.info("test_get_webhook_delivery_not_found() start")

    fake_id = ObjectId()
    response = client.get(
        f"/v0/orgs/{TEST_ORG_ID}/webhook/deliveries/{fake_id}",
        headers=get_auth_headers(),
    )

    assert response.status_code == 404

    logger.info("test_get_webhook_delivery_not_found() end")


@pytest.mark.asyncio
async def test_retry_webhook_delivery(test_db, mock_auth):
    """Test POST /webhook/deliveries/{delivery_id}/retry endpoint"""
    logger.info("test_retry_webhook_delivery() start")

    delivery_id = ObjectId()
    now = datetime.now(UTC)

    await test_db[DELIVERIES_COLLECTION].insert_one({
        "_id": delivery_id,
        "event_id": "evt_retry",
        "event_type": "document.uploaded",
        "organization_id": TEST_ORG_ID,
        "status": "failed",
        "attempts": 10,
        "max_attempts": 10,
        "created_at": now,
        "updated_at": now,
    })

    with patch("analytiq_data.queue.send_msg", new_callable=AsyncMock):
        response = client.post(
            f"/v0/orgs/{TEST_ORG_ID}/webhook/deliveries/{delivery_id}/retry",
            headers=get_auth_headers(),
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "enqueued"
    assert data["delivery_id"] == str(delivery_id)

    # Verify delivery was reset to pending
    delivery = await test_db[DELIVERIES_COLLECTION].find_one({"_id": delivery_id})
    assert delivery["status"] == "pending"

    logger.info("test_retry_webhook_delivery() end")


@pytest.mark.asyncio
async def test_retry_webhook_delivery_not_found(test_db, mock_auth):
    """Test POST /webhook/deliveries/{delivery_id}/retry returns 404"""
    logger.info("test_retry_webhook_delivery_not_found() start")

    fake_id = ObjectId()
    response = client.post(
        f"/v0/orgs/{TEST_ORG_ID}/webhook/deliveries/{fake_id}/retry",
        headers=get_auth_headers(),
    )

    assert response.status_code == 404

    logger.info("test_retry_webhook_delivery_not_found() end")


# ============================================================================
# Message Handler Tests
# ============================================================================


@pytest.mark.asyncio
async def test_process_webhook_msg_success(test_db, mock_auth):
    """Test process_webhook_msg successfully processes a delivery"""
    logger.info("test_process_webhook_msg_success() start")

    delivery_id = ObjectId()
    now = datetime.now(UTC)

    await test_db[DELIVERIES_COLLECTION].insert_one({
        "_id": delivery_id,
        "event_id": "evt_msg",
        "event_type": "webhook.test",
        "organization_id": TEST_ORG_ID,
        "status": "pending",
        "attempts": 0,
        "max_attempts": 10,
        "next_attempt_at": now - timedelta(seconds=1),
        "payload": {"test": True},
        "target_url": "https://example.com/webhook",
        "auth_type": "hmac",
        "secret_encrypted": "secret",
        "created_at": now,
        "updated_at": now,
    })

    msg = {
        "_id": ObjectId(),
        "msg": {"delivery_id": str(delivery_id)},
    }

    analytiq_client = MagicMock()

    class SuccessClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *args, **kwargs):
            resp = MagicMock()
            resp.status_code = 200
            resp.content = b'{"ok":true}'
            resp.text = '{"ok":true}'
            return resp

    with patch("analytiq_data.common.get_async_db", return_value=test_db):
        with patch("analytiq_data.webhooks.dispatch.httpx.AsyncClient", SuccessClient):
            with patch("analytiq_data.queue.delete_msg", new_callable=AsyncMock):
                await process_webhook_msg(analytiq_client, msg)

    # Verify delivery was marked as delivered
    delivery = await test_db[DELIVERIES_COLLECTION].find_one({"_id": delivery_id})
    assert delivery["status"] == "delivered"

    logger.info("test_process_webhook_msg_success() end")


@pytest.mark.asyncio
async def test_process_webhook_msg_missing_delivery_id():
    """Test process_webhook_msg handles missing delivery_id gracefully"""
    logger.info("test_process_webhook_msg_missing_delivery_id() start")

    msg = {
        "_id": ObjectId(),
        "msg": {},  # No delivery_id
    }

    analytiq_client = MagicMock()

    # Should not raise, just log error
    await process_webhook_msg(analytiq_client, msg)

    logger.info("test_process_webhook_msg_missing_delivery_id() end")


@pytest.mark.asyncio
async def test_process_webhook_msg_delivery_not_claimed(test_db, mock_auth):
    """Test process_webhook_msg handles already-claimed delivery"""
    logger.info("test_process_webhook_msg_delivery_not_claimed() start")

    delivery_id = ObjectId()
    now = datetime.now(UTC)

    # Delivery already processing
    await test_db[DELIVERIES_COLLECTION].insert_one({
        "_id": delivery_id,
        "event_id": "evt_msg",
        "event_type": "webhook.test",
        "organization_id": TEST_ORG_ID,
        "status": "processing",
        "attempts": 1,
        "max_attempts": 10,
        "last_attempt_at": now,  # Recently claimed
        "created_at": now,
        "updated_at": now,
    })

    msg = {
        "_id": ObjectId(),
        "msg": {"delivery_id": str(delivery_id)},
    }

    analytiq_client = MagicMock()

    with patch("analytiq_data.common.get_async_db", return_value=test_db):
        with patch("analytiq_data.queue.delete_msg", new_callable=AsyncMock):
            # Should not send delivery since claim returns None
            await process_webhook_msg(analytiq_client, msg)

    # Status should remain processing (not changed)
    delivery = await test_db[DELIVERIES_COLLECTION].find_one({"_id": delivery_id})
    assert delivery["status"] == "processing"

    logger.info("test_process_webhook_msg_delivery_not_claimed() end")
