"""Retry logic with exponential backoff for handling rate limits and transient failures."""

import asyncio
import logging
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

from cryptopilot.providers.base import ProviderError, RateLimitError

logger = logging.getLogger(__name__)

T = TypeVar("T")


class RetryConfig:
    """Configuration for retry behavior."""

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        retry_on: tuple[type[Exception], ...] = (RateLimitError, ProviderError),
    ) -> None:
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.retry_on = retry_on


def calculate_backoff(attempt: int, config: RetryConfig) -> float:
    """Calculate exponential backoff delay.

    Args:
        attempt: Current attempt number (0-indexed)
        config: Retry configuration

    Returns:
        Delay in seconds

    """
    delay = config.base_delay * (config.exponential_base**attempt)
    return min(delay, config.max_delay)


def retry_async(
    config: RetryConfig | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator for async functions with retry logic and exponential backoff.

    Usage:
        @retry_async(RetryConfig(max_retries=5))
        async def fetch_data():
            ...
    """
    if config is None:
        config = RetryConfig()

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: Exception | None = None

            for attempt in range(config.max_retries + 1):
                try:
                    return await func(*args, **kwargs)

                except RateLimitError as e:
                    last_exception = e

                    if e.retry_after is not None:
                        delay = e.retry_after
                    else:
                        delay = calculate_backoff(attempt, config)

                    if attempt < config.max_retries:
                        logger.warning(
                            f"Rate limit hit in {func.__name__}. "
                            f"Retrying in {delay:.1f}s (attempt {attempt + 1}/{config.max_retries})"
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            f"Rate limit exceeded in {func.__name__} after {config.max_retries} retries"
                        )

                except config.retry_on as e:
                    last_exception = e

                    if attempt < config.max_retries:
                        delay = calculate_backoff(attempt, config)
                        logger.warning(
                            f"Error in {func.__name__}: {e}. "
                            f"Retrying in {delay:.1f}s (attempt {attempt + 1}/{config.max_retries})"
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            f"Failed {func.__name__} after {config.max_retries} retries: {e}"
                        )

                except Exception as e:
                    logger.error(f"Unexpected error in {func.__name__}: {e}")
                    raise

            if last_exception:
                raise last_exception

            raise RuntimeError(f"{func.__name__} failed after {config.max_retries} retries")

        return wrapper

    return decorator


async def retry_with_backoff(
    func: Callable[..., T],
    *args: Any,
    config: RetryConfig | None = None,
    **kwargs: Any,
) -> T:
    """Execute async function with retry logic (functional approach).

    Usage:
        result = await retry_with_backoff(
            api.fetch_data,
            symbol="BTC",
            config=RetryConfig(max_retries=5)
        )
    """
    if config is None:
        config = RetryConfig()

    last_exception: Exception | None = None

    for attempt in range(config.max_retries + 1):
        try:
            return await func(*args, **kwargs)

        except RateLimitError as e:
            last_exception = e

            if e.retry_after is not None:
                delay = e.retry_after
            else:
                delay = calculate_backoff(attempt, config)

            if attempt < config.max_retries:
                logger.warning(
                    f"Rate limit hit. Retrying in {delay:.1f}s "
                    f"(attempt {attempt + 1}/{config.max_retries})"
                )
                await asyncio.sleep(delay)
            else:
                logger.error(f"Rate limit exceeded after {config.max_retries} retries")

        except config.retry_on as e:
            last_exception = e

            if attempt < config.max_retries:
                delay = calculate_backoff(attempt, config)
                logger.warning(
                    f"Error: {e}. Retrying in {delay:.1f}s "
                    f"(attempt {attempt + 1}/{config.max_retries})"
                )
                await asyncio.sleep(delay)
            else:
                logger.error(f"Failed after {config.max_retries} retries: {e}")

        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise

    if last_exception:
        raise last_exception

    raise RuntimeError(f"Function failed after {config.max_retries} retries")
