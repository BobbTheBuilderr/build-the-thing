import asyncio
import functools
from typing import Callable, TypeVar, Any
from utils.logger import get_logger

log = get_logger("retry")
T = TypeVar("T")


def with_retry(
    max_attempts: int = 3,
    base_delay: float = 2.0,
    exceptions: tuple = (Exception,),
) -> Callable:
    def decorator(fn: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exc: Exception | None = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return await fn(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc
                    if attempt < max_attempts:
                        delay = base_delay * (2 ** (attempt - 1))
                        log.warning(
                            f"[yellow]{fn.__name__}[/] attempt {attempt} failed: {exc}. "
                            f"Retrying in {delay:.0f}s…"
                        )
                        await asyncio.sleep(delay)
            raise last_exc  # type: ignore[misc]
        return wrapper
    return decorator
