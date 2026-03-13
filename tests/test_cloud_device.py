"""Tests for CloudDevice REST API wrapper."""

import re

import aiohttp
import pytest
from aioresponses import aioresponses

from mcp_airq_cloud.cloud_device import BASE_URL, CloudDevice

DEVICE_ID = "a" * 32
API_KEY = "test-api-key"
LATEST_URL = f"{BASE_URL}/devices/{DEVICE_ID}/sensordata/latest"
TIMERANGE_URL = f"{BASE_URL}/devices/{DEVICE_ID}/sensordata/timerange"


@pytest.fixture
def mock_api():
    with aioresponses() as m:
        yield m


@pytest.fixture
async def session():
    async with aiohttp.ClientSession() as s:
        yield s


@pytest.fixture
def cloud_device(session):
    return CloudDevice(DEVICE_ID, API_KEY, session)


async def test_get_latest_data(mock_api, cloud_device):
    """GET /sensordata/latest returns parsed JSON."""
    payload = {"temperature": 22.5, "co2": 450, "humidity": 55.0}
    mock_api.get(LATEST_URL, payload=payload)

    result = await cloud_device.get_latest_data()
    assert result == payload


async def test_get_latest_data_sends_api_key(mock_api, cloud_device):
    """Request includes Api-Key header."""
    mock_api.get(LATEST_URL, payload={})

    await cloud_device.get_latest_data()

    # Find the request call — aioresponses keys use yarl.URL objects
    for key, calls in mock_api.requests.items():
        if key[0] == "GET" and "latest" in str(key[1]):
            assert calls[0].kwargs["headers"]["Api-Key"] == API_KEY
            return
    pytest.fail("No matching request found")


async def test_get_data_timerange(mock_api, cloud_device):
    """GET /sensordata/timerange returns parsed JSON array."""
    payload = [
        {"temperature": 22.5, "timestamp": 1000},
        {"temperature": 23.0, "timestamp": 2000},
    ]
    # Match URL with any query params
    mock_api.get(re.compile(re.escape(TIMERANGE_URL)), payload=payload)

    result = await cloud_device.get_data_timerange(1000, 2000)
    assert result == payload


async def test_get_data_timerange_sends_params(mock_api, cloud_device):
    """Time range query includes f and t parameters."""
    mock_api.get(re.compile(re.escape(TIMERANGE_URL)), payload=[])

    await cloud_device.get_data_timerange(1740583162166, 1740669562166)

    # Find the request call
    for key, calls in mock_api.requests.items():
        if key[0] == "GET" and "timerange" in str(key[1]):
            assert calls[0].kwargs["params"] == {
                "f": "1740583162166",
                "t": "1740669562166",
            }
            return
    pytest.fail("No matching request found")


async def test_get_latest_data_401(mock_api, cloud_device):
    """401 raises ClientResponseError."""
    mock_api.get(LATEST_URL, status=401)

    with pytest.raises(aiohttp.ClientResponseError) as exc_info:
        await cloud_device.get_latest_data()
    assert exc_info.value.status == 401


async def test_get_latest_data_404(mock_api, cloud_device):
    """404 raises ClientResponseError."""
    mock_api.get(LATEST_URL, status=404)

    with pytest.raises(aiohttp.ClientResponseError) as exc_info:
        await cloud_device.get_latest_data()
    assert exc_info.value.status == 404
