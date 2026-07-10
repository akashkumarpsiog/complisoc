import time
from collections.abc import Callable
from typing import TypeVar


T = TypeVar("T")


def call_with_retry(
    fn: Callable[[], T],
    *,
    attempts: int = 3,
    backoff: float = 1.0,
    delay_for: Callable[[Exception], float | None] | None = None,
    give_up_on: Callable[[Exception], bool] | None = None,
    max_delay: float = 30.0,
) -> T:
    last_exc: Exception | None = None
    for index in range(attempts):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            if index >= attempts - 1:
                break
            if give_up_on is not None and give_up_on(exc):
                break
            delay = delay_for(exc) if delay_for else None
            if delay is None:
                delay = backoff * (2**index)
            time.sleep(min(max_delay, max(0.0, delay)))
    raise last_exc or RuntimeError("Retry failed without an exception.")
