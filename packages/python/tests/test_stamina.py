import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from analytiq_data.llm.llm import (
    is_retryable_connection_error,
    is_retryable_error,
    is_retryable_overloaded_error,
    llm_connection_retry_backoff,
    llm_overloaded_retry_backoff,
    _litellm_acompletion_with_retry,
)


def test_is_retryable_overloaded_error():
    overloaded_exceptions = [
        Exception("503 Service Unavailable"),
        Exception("Model is overloaded"),
        Exception("Service temporarily unavailable"),
        Exception("Rate limit exceeded"),
        Exception(
            'litellm.RateLimitError: Vertex_aiException - {"error": {"code": 429, '
            '"message": "Resource has been exhausted (e.g. check quota).", '
            '"status": "RESOURCE_EXHAUSTED"}}'
        ),
        Exception("Service unavailable"),
    ]
    for exc in overloaded_exceptions:
        assert is_retryable_overloaded_error(exc), f"Exception '{exc}' should be overloaded-retryable"
        assert is_retryable_error(exc)
        assert not is_retryable_connection_error(exc)


def test_is_retryable_connection_error():
    connection_exceptions = [
        Exception("Connection error"),
        Exception("Internal server error"),
        Exception("Connection timeout"),
    ]
    for exc in connection_exceptions:
        assert is_retryable_connection_error(exc), f"Exception '{exc}' should be connection-retryable"
        assert is_retryable_error(exc)
        assert not is_retryable_overloaded_error(exc)


def test_is_retryable_error_with_non_retryable_exceptions():
    """Test that non-retryable exceptions are correctly identified"""
    non_retryable_exceptions = [
        Exception("Invalid API key"),
        Exception("Bad request"),
        Exception("Not found"),
        Exception("Unauthorized"),
        Exception("Forbidden"),
        Exception("Validation error")
    ]

    for exc in non_retryable_exceptions:
        assert not is_retryable_error(exc), f"Exception '{exc}' should not be retryable"
        assert not is_retryable_overloaded_error(exc)
        assert not is_retryable_connection_error(exc)


def test_is_retryable_error_with_non_exception():
    """Test that non-exception objects return False"""
    non_exceptions = [
        "string",
        123,
        None,
        [],
        {},
        True
    ]

    for obj in non_exceptions:
        assert not is_retryable_error(obj), f"Object '{obj}' should not be retryable"


def test_llm_overloaded_retry_backoff_returns_fixed_wait():
    exc = Exception("429 Too Many Requests")
    assert llm_overloaded_retry_backoff(exc) == 15.0


def test_llm_connection_retry_backoff_uses_exponential():
    assert llm_connection_retry_backoff(Exception("Connection error")) is True
    assert llm_connection_retry_backoff(Exception("429 Too Many Requests")) is False


def test_overloaded_errors_do_not_use_connection_backoff_after_inner_exhausted():
    exc = Exception("503 Service Unavailable")
    assert llm_overloaded_retry_backoff(exc) == 15.0
    assert llm_connection_retry_backoff(exc) is False


@pytest.mark.asyncio
async def test_successful_completion_no_retry():
    """Test that successful completion works without retry"""
    mock_response = AsyncMock()
    mock_response.choices = [AsyncMock()]
    mock_response.choices[0].message = AsyncMock()
    mock_response.choices[0].message.content = '{"result": "success"}'

    with patch('analytiq_data.llm.llm.litellm.acompletion', return_value=mock_response) as mock_acompletion:
        result = await _litellm_acompletion_with_retry(
            analytiq_client=None,
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "test"}],
            api_key="test-key"
        )

        assert mock_acompletion.call_count == 1
        assert result == mock_response


@pytest.mark.asyncio
async def test_overloaded_error_retries_and_succeeds():
    """Overloaded errors use inner 15s-linear retry layer."""
    mock_success_response = AsyncMock()
    mock_success_response.choices = [AsyncMock()]
    mock_success_response.choices[0].message = AsyncMock()
    mock_success_response.choices[0].message.content = '{"result": "success"}'

    with patch('stamina._core._smart_sleep', new_callable=AsyncMock), \
         patch('analytiq_data.llm.llm.litellm.acompletion') as mock_acompletion:
        mock_acompletion.side_effect = [
            Exception("503 Service Unavailable"),
            mock_success_response,
        ]

        result = await _litellm_acompletion_with_retry(
            analytiq_client=None,
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "test"}],
            api_key="test-key"
        )

        assert mock_acompletion.call_count == 2
        assert result == mock_success_response


@pytest.mark.asyncio
async def test_connection_error_retries_and_succeeds():
    """Connection errors use outer default exponential retry layer."""
    mock_success_response = AsyncMock()
    mock_success_response.choices = [AsyncMock()]
    mock_success_response.choices[0].message = AsyncMock()
    mock_success_response.choices[0].message.content = '{"result": "success"}'

    with patch('stamina._core._smart_sleep', new_callable=AsyncMock), \
         patch('analytiq_data.llm.llm.litellm.acompletion') as mock_acompletion:
        mock_acompletion.side_effect = [
            Exception("Connection error"),
            mock_success_response,
        ]

        result = await _litellm_acompletion_with_retry(
            analytiq_client=None,
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "test"}],
            api_key="test-key"
        )

        assert mock_acompletion.call_count == 2
        assert result == mock_success_response


@pytest.mark.asyncio
async def test_non_retryable_error_no_retry():
    """Test that non-retryable errors don't trigger retries"""
    with patch('analytiq_data.llm.llm.litellm.acompletion') as mock_acompletion:
        mock_acompletion.side_effect = Exception("Invalid API key")

        with pytest.raises(Exception, match="Invalid API key"):
            await _litellm_acompletion_with_retry(
                None,
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": "test"}],
                api_key="test-key"
            )

        assert mock_acompletion.call_count == 1


@pytest.mark.asyncio
async def test_multiple_overloaded_errors_eventually_succeeds():
    """Multiple overloaded errors retry on inner layer only."""
    mock_success_response = AsyncMock()
    mock_success_response.choices = [AsyncMock()]
    mock_success_response.choices[0].message = AsyncMock()
    mock_success_response.choices[0].message.content = '{"result": "success"}'

    with patch('stamina._core._smart_sleep', new_callable=AsyncMock), \
         patch('analytiq_data.llm.llm.litellm.acompletion') as mock_acompletion:
        mock_acompletion.side_effect = [
            Exception("503 Service Unavailable"),
            Exception("Rate limit exceeded"),
            Exception("Model is overloaded"),
            mock_success_response,
        ]

        result = await _litellm_acompletion_with_retry(
            analytiq_client=None,
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "test"}],
            api_key="test-key"
        )

        assert mock_acompletion.call_count == 4
        assert result == mock_success_response


@pytest.mark.asyncio
async def test_retry_with_aws_parameters():
    """Test that retry works with AWS Bedrock — add_aws_params is called to inject credentials."""
    mock_response = AsyncMock()
    mock_response.choices = [AsyncMock()]
    mock_response.choices[0].message = AsyncMock()
    mock_response.choices[0].message.content = '{"result": "success"}'

    mock_analytiq_client = AsyncMock()

    async def fake_add_aws_params(analytiq_client, params):
        params["aws_access_key_id"] = "test-access-key"
        params["aws_secret_access_key"] = "test-secret-key"
        params["aws_region_name"] = "us-east-1"

    with patch('analytiq_data.llm.llm.litellm.acompletion', return_value=mock_response) as mock_acompletion, \
         patch('analytiq_data.llm.llm_aws.add_aws_params', side_effect=fake_add_aws_params):
        result = await _litellm_acompletion_with_retry(
            mock_analytiq_client,
            model="bedrock/claude-3-sonnet-20240229-v1:0",
            messages=[{"role": "user", "content": "test"}],
            api_key="test-key",
        )

        assert mock_acompletion.call_count == 1
        call_args = mock_acompletion.call_args
        assert call_args[1]['aws_access_key_id'] == "test-access-key"
        assert call_args[1]['aws_secret_access_key'] == "test-secret-key"
        assert call_args[1]['aws_region_name'] == "us-east-1"
        assert result == mock_response
