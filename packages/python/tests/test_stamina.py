import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from analytiq_data.llm.llm import is_retryable_error, _litellm_acompletion_with_retry


def test_is_retryable_error_with_retryable_exceptions():
    """Test that retryable exceptions are correctly identified"""
    retryable_exceptions = [
        Exception("503 Service Unavailable"),
        Exception("Model is overloaded"),
        Exception("Service temporarily unavailable"),
        Exception("Rate limit exceeded"),
        Exception("Connection timeout"),
        Exception("Internal server error"),
        Exception("Service unavailable")
    ]
    
    for exc in retryable_exceptions:
        assert is_retryable_error(exc), f"Exception '{exc}' should be retryable"


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


@pytest.mark.asyncio
async def test_successful_completion_no_retry():
    """Test that successful completion works without retry"""
    # Mock successful response
    mock_response = AsyncMock()
    mock_response.choices = [AsyncMock()]
    mock_response.choices[0].message = AsyncMock()
    mock_response.choices[0].message.content = '{"result": "success"}'
    
    with patch('analytiq_data.llm.llm.litellm.acompletion', return_value=mock_response) as mock_acompletion:
        result = await _litellm_acompletion_with_retry(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "test"}],
            api_key="test-key"
        )
        
        # Verify the function was called once (no retry)
        assert mock_acompletion.call_count == 1
        assert result == mock_response


@pytest.mark.asyncio
async def test_retryable_error_retries_and_succeeds():
    """Test that retryable errors trigger retries and eventually succeed"""
    # Mock response that fails first, then succeeds
    mock_success_response = AsyncMock()
    mock_success_response.choices = [AsyncMock()]
    mock_success_response.choices[0].message = AsyncMock()
    mock_success_response.choices[0].message.content = '{"result": "success"}'
    
    # First call fails with retryable error, second call succeeds
    with patch('analytiq_data.llm.llm.litellm.acompletion') as mock_acompletion:
        mock_acompletion.side_effect = [
            Exception("503 Service Unavailable"),  # First call fails
            mock_success_response  # Second call succeeds
        ]
        
        result = await _litellm_acompletion_with_retry(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "test"}],
            api_key="test-key"
        )
        
        # Verify the function was called twice (retry happened)
        assert mock_acompletion.call_count == 2
        assert result == mock_success_response


@pytest.mark.asyncio
async def test_non_retryable_error_no_retry():
    """Test that non-retryable errors don't trigger retries"""
    with patch('analytiq_data.llm.llm.litellm.acompletion') as mock_acompletion:
        mock_acompletion.side_effect = Exception("Invalid API key")
        
        with pytest.raises(Exception, match="Invalid API key"):
            await _litellm_acompletion_with_retry(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": "test"}],
                api_key="test-key"
            )
        
        # Verify the function was called only once (no retry)
        assert mock_acompletion.call_count == 1


@pytest.mark.asyncio
async def test_multiple_retryable_errors_eventually_succeeds():
    """Test that multiple retryable errors eventually succeed"""
    mock_success_response = AsyncMock()
    mock_success_response.choices = [AsyncMock()]
    mock_success_response.choices[0].message = AsyncMock()
    mock_success_response.choices[0].message.content = '{"result": "success"}'
    
    with patch('analytiq_data.llm.llm.litellm.acompletion') as mock_acompletion:
        mock_acompletion.side_effect = [
            Exception("503 Service Unavailable"),  # First call fails
            Exception("Rate limit exceeded"),      # Second call fails
            Exception("Model is overloaded"),      # Third call fails
            mock_success_response                  # Fourth call succeeds
        ]
        
        result = await _litellm_acompletion_with_retry(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "test"}],
            api_key="test-key"
        )
        
        # Verify the function was called four times (3 retries)
        assert mock_acompletion.call_count == 4
        assert result == mock_success_response


@pytest.mark.asyncio
async def test_retry_with_aws_parameters():
    """Test that retry works with AWS parameters for Bedrock"""
    mock_response = AsyncMock()
    mock_response.choices = [AsyncMock()]
    mock_response.choices[0].message = AsyncMock()
    mock_response.choices[0].message.content = '{"result": "success"}'
    
    with patch('analytiq_data.llm.llm.litellm.acompletion', return_value=mock_response) as mock_acompletion:
        result = await _litellm_acompletion_with_retry(
            model="claude-3-sonnet-20240229-v1:0",
            messages=[{"role": "user", "content": "test"}],
            api_key="test-key",
            aws_access_key_id="test-access-key",
            aws_secret_access_key="test-secret-key",
            aws_region_name="us-east-1"
        )
        
        # Verify the function was called with AWS parameters
        assert mock_acompletion.call_count == 1
        call_args = mock_acompletion.call_args
        assert call_args[1]['aws_access_key_id'] == "test-access-key"
        assert call_args[1]['aws_secret_access_key'] == "test-secret-key"
        assert call_args[1]['aws_region_name'] == "us-east-1"
        assert result == mock_response
