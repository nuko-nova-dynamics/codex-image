"""Retry policy per spec §10: 5xx + network → exponential backoff with jitter."""
from __future__ import annotations

import random
import time
import urllib.error
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")
MAX_RETRY_AFTER_SECONDS = 30


class RetryGivenUp(Exception):
    pass


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, urllib.error.HTTPError):
        return 500 <= exc.code <= 599
    if isinstance(exc, urllib.error.URLError):
        return True  # network / DNS / TLS
    # Spec §10: SSE idle timeouts surface to the user, never auto-retry.
    return False


def _retry_after_seconds(exc: BaseException) -> int | None:
    if not isinstance(exc, urllib.error.HTTPError) or not exc.headers:
        return None
    value = exc.headers.get("Retry-After")
    if value is None:
        return None
    try:
        seconds = int(value)
    except (TypeError, ValueError):
        return None
    return min(max(seconds, 0), MAX_RETRY_AFTER_SECONDS)


def call_with_retries(
    fn: Callable[[], T],
    *,
    max_attempts: int = 4,
    base_delay: float = 0.2,
) -> T:
    """Call fn; retry on 5xx + network with exponential backoff and [0.9, 1.1) jitter."""
    last: BaseException | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except BaseException as e:
            last = e
            if not _is_retryable(e) or attempt == max_attempts:
                raise
            retry_after = _retry_after_seconds(e)
            delay = (
                retry_after
                if retry_after is not None
                else base_delay * (2 ** (attempt - 1)) * random.uniform(0.9, 1.1)
            )
            time.sleep(delay)
    assert last is not None
    raise last
