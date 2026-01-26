"""
Retry utility for handling transient failures in API calls.

This module provides a reusable retry mechanism that extracts
the duplicate retry logic from sheets_writer.py into a single place.

Benefits:
- DRY: Fix bugs once, not in multiple places
- Testable: Easy to test retry behavior with mock operations
- Configurable: Customize retries, delays, and error handling
"""

import time
import logging
from dataclasses import dataclass, field
from typing import Callable, TypeVar, Optional, Any, Tuple

logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class RetryResult:
    """
    Result of a retryable operation.

    This class encapsulates the outcome of an operation that may have
    been retried multiple times. It provides a clear interface for
    checking success/failure without using exceptions for control flow.

    Attributes:
        success: True if the operation succeeded
        value: The return value if successful, None otherwise
        error: The exception if failed, None otherwise
        attempts: Number of attempts made

    Example:
        >>> result = retry_operation(lambda: api_call())
        >>> if result.success:
        ...     print(f"Got result: {result.value}")
        ... else:
        ...     print(f"Failed after {result.attempts} attempts: {result.error}")
    """
    success: bool
    value: Optional[Any] = None
    error: Optional[Exception] = None
    attempts: int = 0


def retry_operation(
    operation: Callable[[], T],
    max_retries: int = 3,
    base_delay: float = 2.0,
    non_retryable_codes: Tuple[int, ...] = (403, 404),
    retryable_codes: Tuple[int, ...] = (429, 500, 502, 503, 504),
    on_retry: Optional[Callable[[int, Exception], None]] = None,
) -> RetryResult:
    """
    Execute an operation with automatic retry on failure.

    This function wraps an operation and handles transient failures
    by retrying with linear backoff. It's designed for API calls that
    may fail due to rate limiting or temporary issues.

    Args:
        operation: A callable that performs the operation. Should take
            no arguments (use a closure or lambda to capture any needed values).
        max_retries: Maximum number of attempts before giving up.
        base_delay: Initial delay between retries in seconds.
            The actual delay is base_delay * attempt_number (linear backoff).
        non_retryable_codes: HTTP status codes that should fail immediately
            without retrying. Default: (403, 404) for permission/not found.
        retryable_codes: HTTP status codes that should trigger a retry.
            Default: (429, 500, 502, 503, 504) for rate limit and server errors.
        on_retry: Optional callback called before each retry. Receives
            (attempt_number, exception) as arguments. Useful for custom logging.

    Returns:
        RetryResult containing:
        - success: True if operation succeeded
        - value: The operation's return value (if successful)
        - error: The last exception (if failed)
        - attempts: Total number of attempts made

    Backoff Strategy:
        Uses linear backoff: delay = base_delay * attempt_number
        - Attempt 1 fails -> wait base_delay seconds (e.g., 2s)
        - Attempt 2 fails -> wait base_delay * 2 seconds (e.g., 4s)
        - Attempt 3 fails -> wait base_delay * 3 seconds (e.g., 6s)

    Example:
        >>> def call_api():
        ...     return requests.get("https://api.example.com/data").json()
        ...
        >>> result = retry_operation(
        ...     operation=call_api,
        ...     max_retries=3,
        ...     base_delay=1.0
        ... )
        >>> if result.success:
        ...     process(result.value)
    """
    last_error: Optional[Exception] = None

    for attempt in range(1, max_retries + 1):
        try:
            value = operation()
            return RetryResult(success=True, value=value, attempts=attempt)

        except Exception as e:
            last_error = e

            # Check if this is an HTTP error with a status code
            # Works with googleapiclient.errors.HttpError
            status_code = _get_http_status(e)

            if status_code is not None:
                # Non-retryable HTTP errors - fail immediately
                if status_code in non_retryable_codes:
                    logger.error(
                        f"Non-retryable HTTP error {status_code}: {e}"
                    )
                    return RetryResult(
                        success=False,
                        error=e,
                        attempts=attempt
                    )

                # Log retryable HTTP errors
                if status_code in retryable_codes:
                    logger.warning(
                        f"Retryable HTTP error {status_code}, "
                        f"attempt {attempt}/{max_retries}"
                    )
                else:
                    logger.error(f"HTTP error {status_code}: {e}")
            else:
                # Non-HTTP exception
                logger.error(
                    f"Error on attempt {attempt}/{max_retries}: "
                    f"{type(e).__name__}: {e}"
                )

            # Check if we should retry
            if attempt < max_retries:
                delay = base_delay * attempt
                logger.info(f"Retrying in {delay:.1f}s...")

                # Call optional retry callback
                if on_retry:
                    on_retry(attempt, e)

                time.sleep(delay)

    # All retries exhausted
    logger.error(f"All {max_retries} attempts failed")
    return RetryResult(
        success=False,
        error=last_error,
        attempts=max_retries
    )


def _get_http_status(error: Exception) -> Optional[int]:
    """
    Extract HTTP status code from an exception if available.

    Works with googleapiclient.errors.HttpError and similar classes
    that have a resp.status attribute.

    Args:
        error: The exception to check

    Returns:
        HTTP status code if available, None otherwise
    """
    # Try googleapiclient.errors.HttpError pattern
    if hasattr(error, 'resp') and hasattr(error.resp, 'status'):
        return error.resp.status

    # Try requests.HTTPError pattern
    if hasattr(error, 'response') and hasattr(error.response, 'status_code'):
        return error.response.status_code

    return None


def is_retryable_error(
    error: Exception,
    non_retryable_codes: Tuple[int, ...] = (403, 404),
    retryable_codes: Tuple[int, ...] = (429, 500, 502, 503, 504),
) -> bool:
    """
    Determine if an error should be retried.

    This is a helper function for cases where you need to check
    retryability outside of the retry_operation function.

    Args:
        error: The exception to check
        non_retryable_codes: HTTP status codes that should not be retried
        retryable_codes: HTTP status codes that should be retried

    Returns:
        True if the error should be retried, False otherwise
    """
    status_code = _get_http_status(error)

    if status_code is not None:
        if status_code in non_retryable_codes:
            return False
        return status_code in retryable_codes

    # For non-HTTP errors, default to retrying
    return True
