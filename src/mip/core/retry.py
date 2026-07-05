"""Retry decorator with exponential backoff.

Retries only TransientError (or the exception types passed in); anything
else propagates immediately. The sleep function is injectable so tests
run instantly and can assert the backoff sequence.
"""

import time
from collections.abc import Callable
from functools import wraps

from mip.core.exceptions import TransientError
from mip.core.logging import get_logger

logger = get_logger(__name__)


def retry[**P, R](
    max_attempts: int = 4,
    backoff_seconds: float = 1.0,
    retry_on: tuple[type[Exception], ...] = (TransientError,),
    sleep: Callable[[float], None] = time.sleep,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except retry_on as exc:
                    if attempt == max_attempts:
                        logger.error(
                            "retry.exhausted",
                            func=func.__qualname__,
                            attempts=attempt,
                            error=str(exc),
                        )
                        raise
                    delay = backoff_seconds * 2 ** (attempt - 1)
                    logger.warning(
                        "retry.attempt_failed",
                        func=func.__qualname__,
                        attempt=attempt,
                        next_delay_seconds=delay,
                        error=str(exc),
                    )
                    sleep(delay)
            raise AssertionError("unreachable")  # loop always returns or raises

        return wrapper

    return decorator
