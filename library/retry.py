"""Shared retry decorator for calls to external services."""
from __future__ import annotations

import functools
import time
from typing import Any, Callable, Tuple, Type


def retry(
    times: int = 3,
    exceptions: Tuple[Type[BaseException], ...] = (Exception,),
    delay: float = 1.0,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Retry `times` attempts with linear back-off (delay, 2*delay, ...)."""

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            for attempt in range(times):
                try:
                    return fn(*args, **kwargs)
                except exceptions:
                    if attempt == times - 1:
                        raise
                    time.sleep(delay * (attempt + 1))

        return wrapper

    return decorator
