"""
Unit tests for the retry utility.

Run with: pytest tests/test_retry.py -v

These tests demonstrate the retry utility behavior:
1. Successful operations return immediately
2. Transient failures are retried with backoff
3. Non-retryable errors fail immediately
4. All retries exhausted returns failure result
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import time

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.retry import (
    retry_operation,
    RetryResult,
    is_retryable_error,
    _get_http_status
)


class TestRetryResult:
    """Tests for the RetryResult dataclass."""

    def test_success_result(self):
        """Test creating a success result."""
        result = RetryResult(success=True, value=42, attempts=1)

        assert result.success is True
        assert result.value == 42
        assert result.error is None
        assert result.attempts == 1

    def test_failure_result(self):
        """Test creating a failure result."""
        error = Exception("Something went wrong")
        result = RetryResult(success=False, error=error, attempts=3)

        assert result.success is False
        assert result.value is None
        assert result.error is error
        assert result.attempts == 3


class TestRetryOperationSuccess:
    """Tests for successful retry operations."""

    def test_successful_operation_returns_immediately(self):
        """Test that successful operation returns on first try."""
        result = retry_operation(lambda: 42)

        assert result.success is True
        assert result.value == 42
        assert result.attempts == 1

    def test_successful_operation_with_complex_return(self):
        """Test successful operation with complex return value."""
        expected = {"key": "value", "list": [1, 2, 3]}
        result = retry_operation(lambda: expected)

        assert result.success is True
        assert result.value == expected


class TestRetryOperationRetries:
    """Tests for retry behavior."""

    def test_retries_on_failure_then_succeeds(self):
        """Test that operation is retried and eventually succeeds."""
        attempts = []

        def failing_twice():
            attempts.append(1)
            if len(attempts) < 3:
                raise Exception("Temporary failure")
            return "success"

        # Use very small delay for fast tests
        result = retry_operation(
            operation=failing_twice,
            max_retries=3,
            base_delay=0.01
        )

        assert result.success is True
        assert result.value == "success"
        assert len(attempts) == 3
        assert result.attempts == 3

    def test_all_retries_exhausted(self):
        """Test that all retries being exhausted returns failure."""
        attempts = []

        def always_fails():
            attempts.append(1)
            raise Exception("Always fails")

        result = retry_operation(
            operation=always_fails,
            max_retries=3,
            base_delay=0.01
        )

        assert result.success is False
        assert result.error is not None
        assert str(result.error) == "Always fails"
        assert len(attempts) == 3
        assert result.attempts == 3

    def test_backoff_delay_increases(self):
        """Test that backoff delay increases with each attempt."""
        attempts_with_time = []
        start_time = time.time()

        def always_fails():
            attempts_with_time.append(time.time() - start_time)
            raise Exception("Fail")

        retry_operation(
            operation=always_fails,
            max_retries=3,
            base_delay=0.1  # 100ms base delay
        )

        # Verify timing: attempt 1 at ~0s, attempt 2 at ~0.1s, attempt 3 at ~0.3s
        assert len(attempts_with_time) == 3
        # First attempt should be immediate
        assert attempts_with_time[0] < 0.05
        # Second attempt after base_delay * 1 = 0.1s
        assert 0.08 < attempts_with_time[1] < 0.2
        # Third attempt after base_delay * 1 + base_delay * 2 = 0.3s
        assert 0.25 < attempts_with_time[2] < 0.5


class FakeHttpError(Exception):
    """Fake HTTP error that mimics googleapiclient.errors.HttpError."""

    def __init__(self, status: int):
        super().__init__(f"HTTP Error {status}")
        self.resp = MagicMock()
        self.resp.status = status


class TestRetryOperationHttpErrors:
    """Tests for HTTP error handling."""

    def test_non_retryable_403_fails_immediately(self):
        """Test that 403 error fails without retrying."""
        attempts = []

        def raises_403():
            attempts.append(1)
            raise FakeHttpError(403)

        result = retry_operation(
            operation=raises_403,
            max_retries=3,
            base_delay=0.01
        )

        assert result.success is False
        assert len(attempts) == 1  # Only one attempt (no retries)
        assert result.attempts == 1

    def test_non_retryable_404_fails_immediately(self):
        """Test that 404 error fails without retrying."""
        attempts = []

        def raises_404():
            attempts.append(1)
            raise FakeHttpError(404)

        result = retry_operation(
            operation=raises_404,
            max_retries=3,
            base_delay=0.01
        )

        assert result.success is False
        assert len(attempts) == 1

    def test_retryable_429_is_retried(self):
        """Test that 429 (rate limit) error is retried."""
        attempts = []

        def raises_429_twice():
            attempts.append(1)
            if len(attempts) < 3:
                raise FakeHttpError(429)
            return "success"

        result = retry_operation(
            operation=raises_429_twice,
            max_retries=3,
            base_delay=0.01
        )

        assert result.success is True
        assert len(attempts) == 3

    def test_retryable_500_is_retried(self):
        """Test that 500 (server error) is retried."""
        attempts = []

        def raises_500_once():
            attempts.append(1)
            if len(attempts) == 1:
                raise FakeHttpError(500)
            return "success"

        result = retry_operation(
            operation=raises_500_once,
            max_retries=3,
            base_delay=0.01
        )

        assert result.success is True
        assert len(attempts) == 2


class TestRetryOperationCallback:
    """Tests for on_retry callback."""

    def test_on_retry_callback_is_called(self):
        """Test that on_retry callback is called before each retry."""
        callback_calls = []

        def on_retry(attempt, error):
            callback_calls.append((attempt, str(error)))

        def fails_twice():
            if len(callback_calls) < 2:
                raise Exception(f"Fail {len(callback_calls) + 1}")
            return "success"

        result = retry_operation(
            operation=fails_twice,
            max_retries=3,
            base_delay=0.01,
            on_retry=on_retry
        )

        assert result.success is True
        assert len(callback_calls) == 2
        assert callback_calls[0] == (1, "Fail 1")
        assert callback_calls[1] == (2, "Fail 2")


class TestGetHttpStatus:
    """Tests for _get_http_status helper."""

    def test_extracts_status_from_googleapiclient_error(self):
        """Test extracting status from googleapiclient.errors.HttpError pattern."""
        mock_error = MagicMock()
        mock_error.resp = MagicMock()
        mock_error.resp.status = 429

        assert _get_http_status(mock_error) == 429

    def test_extracts_status_from_requests_error(self):
        """Test extracting status from requests.HTTPError pattern."""
        mock_error = MagicMock()
        mock_error.response = MagicMock()
        mock_error.response.status_code = 500
        # Remove resp attribute so it doesn't match first pattern
        del mock_error.resp

        assert _get_http_status(mock_error) == 500

    def test_returns_none_for_non_http_error(self):
        """Test returns None for exceptions without HTTP status."""
        error = ValueError("Not an HTTP error")
        assert _get_http_status(error) is None


class TestIsRetryableError:
    """Tests for is_retryable_error helper."""

    def test_403_is_not_retryable(self):
        """Test that 403 is not retryable by default."""
        mock_error = MagicMock()
        mock_error.resp = MagicMock()
        mock_error.resp.status = 403

        assert is_retryable_error(mock_error) is False

    def test_429_is_retryable(self):
        """Test that 429 is retryable by default."""
        mock_error = MagicMock()
        mock_error.resp = MagicMock()
        mock_error.resp.status = 429

        assert is_retryable_error(mock_error) is True

    def test_non_http_error_is_retryable(self):
        """Test that non-HTTP errors are retryable by default."""
        error = Exception("Network timeout")
        assert is_retryable_error(error) is True

    def test_custom_non_retryable_codes(self):
        """Test custom non-retryable codes."""
        mock_error = MagicMock()
        mock_error.resp = MagicMock()
        mock_error.resp.status = 400

        result = is_retryable_error(
            mock_error,
            non_retryable_codes=(400, 401)
        )

        assert result is False
