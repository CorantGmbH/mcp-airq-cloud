"""Shared test fixtures."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mcp_airq_cloud.config import DeviceConfig
from mcp_airq_cloud.devices import DeviceManager

DEVICE_ID_A = "a" * 32
DEVICE_ID_B = "b" * 32
DEVICE_ID_C = "c" * 32


@pytest.fixture
def mock_session():
    """A mock aiohttp.ClientSession."""
    return MagicMock()


@pytest.fixture
def single_device_configs():
    """Config list with one device."""
    return [DeviceConfig(DEVICE_ID_A, "key1", "TestDevice")]


@pytest.fixture
def multi_device_configs():
    """Config list with multiple devices, some sharing a location and group."""
    return [
        DeviceConfig(
            DEVICE_ID_A,
            "key1",
            "Living Room",
            location="Wohnzimmer",
            group="zu Hause",
        ),
        DeviceConfig(DEVICE_ID_B, "key2", "Office", group="Arbeit"),
        DeviceConfig(
            DEVICE_ID_C,
            "key3",
            "Bedroom",
            location="Wohnzimmer",
            group="zu Hause",
        ),
    ]


@pytest.fixture
def single_device_manager(mock_session, single_device_configs):
    """DeviceManager with one device."""
    return DeviceManager(mock_session, single_device_configs)


@pytest.fixture
def multi_device_manager(mock_session, multi_device_configs):
    """DeviceManager with multiple devices."""
    return DeviceManager(mock_session, multi_device_configs)
