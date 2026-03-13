"""Error handling utilities for MCP tool functions."""

import functools
import logging
from collections.abc import Callable

import aiohttp

logger = logging.getLogger(__name__)


def handle_cloud_errors(fn: Callable) -> Callable:
    """Decorator that catches Cloud API and network exceptions,
    returning user-friendly error strings instead of crashing.
    """

    @functools.wraps(fn)
    async def wrapper(*args, **kwargs):
        try:
            return await fn(*args, **kwargs)
        except ValueError as exc:
            logger.debug("Configuration error in %s: %s", fn.__name__, exc)
            return f"Configuration error: {exc}"
        except aiohttp.ClientResponseError as exc:
            if exc.status == 401:
                logger.warning("Authentication failed in %s", fn.__name__)
                return "Authentication failed. Check the API key."
            if exc.status == 403:
                logger.warning("Access denied in %s", fn.__name__)
                return "Access denied for this device."
            if exc.status == 404:
                logger.warning("Device not found in %s", fn.__name__)
                return "Device not found in cloud. Check the device ID."
            logger.error(
                "Cloud API error in %s: HTTP %d: %s",
                fn.__name__,
                exc.status,
                exc.message,
                exc_info=True,
            )
            return f"Cloud API error (HTTP {exc.status}): {exc.message}"
        except aiohttp.ClientError as exc:
            logger.error("Network error in %s: %s", fn.__name__, exc, exc_info=True)
            return f"Network error: {type(exc).__name__}: {exc}"
        except TimeoutError:
            logger.warning("Timeout in %s", fn.__name__)
            return "Request timed out. Check your internet connection."

    return wrapper
