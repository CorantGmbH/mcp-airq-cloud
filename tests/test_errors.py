"""Tests for the @handle_cloud_errors decorator."""

from unittest.mock import MagicMock

import aiohttp

from mcp_airq_cloud.errors import handle_cloud_errors


def make_failing_tool(exc):
    """Return a decorated async function that raises exc."""

    @handle_cloud_errors
    async def tool():
        raise exc

    return tool


def _make_response_error(status, message="error"):
    """Create an aiohttp.ClientResponseError with the given status."""
    return aiohttp.ClientResponseError(
        request_info=MagicMock(),
        history=(),
        status=status,
        message=message,
    )


async def test_handles_value_error():
    result = await make_failing_tool(ValueError("bad config"))()
    assert "Configuration error" in result
    assert "bad config" in result


async def test_handles_401_unauthorized():
    result = await make_failing_tool(_make_response_error(401))()
    assert "Authentication failed" in result
    assert "API key" in result


async def test_handles_403_forbidden():
    result = await make_failing_tool(_make_response_error(403))()
    assert "Access denied" in result


async def test_handles_404_not_found():
    result = await make_failing_tool(_make_response_error(404))()
    assert "Device not found" in result
    assert "device ID" in result


async def test_handles_500_server_error():
    result = await make_failing_tool(_make_response_error(500, "Internal"))()
    assert "Cloud API error" in result
    assert "500" in result


async def test_handles_client_error():
    result = await make_failing_tool(aiohttp.ClientError())()
    assert "Network error" in result


async def test_handles_timeout_error():
    result = await make_failing_tool(TimeoutError())()
    assert "timed out" in result.lower()


async def test_passes_through_return_value():
    @handle_cloud_errors
    async def tool():
        return "ok"

    result = await tool()
    assert result == "ok"
