"""Tests for DeviceManager device resolution."""

from unittest.mock import MagicMock

import pytest

from mcp_airq_cloud.cloud_device import CloudDevice
from mcp_airq_cloud.config import DeviceConfig
from mcp_airq_cloud.devices import DeviceManager

DEVICE_ID_A = "a" * 32
DEVICE_ID_B = "b" * 32
DEVICE_ID_C = "c" * 32


@pytest.fixture
def mock_session():
    return MagicMock()


@pytest.fixture
def single_device_configs():
    return [DeviceConfig(DEVICE_ID_A, "key1", "TestDevice")]


@pytest.fixture
def multi_device_configs():
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
    return DeviceManager(mock_session, single_device_configs)


@pytest.fixture
def multi_device_manager(mock_session, multi_device_configs):
    return DeviceManager(mock_session, multi_device_configs)


def test_device_names(multi_device_manager):
    """device_names returns all configured names."""
    assert multi_device_manager.device_names == [
        "Living Room",
        "Office",
        "Bedroom",
    ]


def test_single_device_auto_resolve(single_device_manager):
    """With one device, resolve(None) returns it."""
    device = single_device_manager.resolve(None)
    assert isinstance(device, CloudDevice)


def test_multi_device_none_raises(multi_device_manager):
    """With multiple devices, resolve(None) raises."""
    with pytest.raises(ValueError, match="Multiple devices"):
        multi_device_manager.resolve(None)


def test_exact_match(multi_device_manager):
    """Exact name match works."""
    device = multi_device_manager.resolve("Office")
    assert isinstance(device, CloudDevice)


def test_substring_match(multi_device_manager):
    """Case-insensitive substring match works."""
    device = multi_device_manager.resolve("office")
    assert isinstance(device, CloudDevice)


def test_partial_match(multi_device_manager):
    """Partial name match works if unambiguous."""
    device = multi_device_manager.resolve("Bed")
    assert isinstance(device, CloudDevice)


def test_ambiguous_match_raises(multi_device_manager):
    """Ambiguous substring raises."""
    # "room" matches "Living Room" and "Bedroom"
    with pytest.raises(ValueError, match="Ambiguous"):
        multi_device_manager.resolve("room")


def test_no_match_raises(multi_device_manager):
    """No match raises with available devices."""
    with pytest.raises(ValueError, match="No device matching"):
        multi_device_manager.resolve("Kitchen")


def test_instance_caching(single_device_manager):
    """Same device name returns the same CloudDevice instance."""
    a = single_device_manager.resolve("TestDevice")
    b = single_device_manager.resolve("TestDevice")
    assert a is b


def test_get_config_for(single_device_manager):
    """get_config_for returns the DeviceConfig."""
    cfg = single_device_manager.get_config_for("TestDevice")
    assert cfg.id == DEVICE_ID_A
    assert cfg.api_key == "key1"


def test_locations(multi_device_manager):
    """locations returns unique configured locations."""
    assert multi_device_manager.locations == ["Wohnzimmer"]


def test_resolve_location(multi_device_manager):
    """resolve_location returns all devices at a location."""
    devices = multi_device_manager.resolve_location("Wohnzimmer")
    names = [name for name, _ in devices]
    assert names == ["Living Room", "Bedroom"]


def test_resolve_location_substring(multi_device_manager):
    """resolve_location supports case-insensitive substring matching."""
    devices = multi_device_manager.resolve_location("wohnz")
    assert len(devices) == 2


def test_resolve_location_no_match(multi_device_manager):
    """resolve_location raises on no match."""
    with pytest.raises(ValueError, match="No devices with location"):
        multi_device_manager.resolve_location("Küche")


def test_resolve_location_no_locations(single_device_manager):
    """resolve_location raises when no locations are configured."""
    with pytest.raises(ValueError, match="No locations configured"):
        single_device_manager.resolve_location("Anywhere")


def test_groups(multi_device_manager):
    """groups returns unique configured groups."""
    assert set(multi_device_manager.groups) == {"zu Hause", "Arbeit"}


def test_resolve_group(multi_device_manager):
    """resolve_group returns all devices in a group."""
    devices = multi_device_manager.resolve_group("zu Hause")
    names = [name for name, _ in devices]
    assert names == ["Living Room", "Bedroom"]


def test_resolve_group_substring(multi_device_manager):
    """resolve_group supports case-insensitive substring matching."""
    devices = multi_device_manager.resolve_group("hause")
    assert len(devices) == 2


def test_resolve_group_no_match(multi_device_manager):
    """resolve_group raises on no match."""
    with pytest.raises(ValueError, match="No devices with group"):
        multi_device_manager.resolve_group("Urlaub")


def test_resolve_group_no_groups(single_device_manager):
    """resolve_group raises when no groups are configured."""
    with pytest.raises(ValueError, match="No groups configured"):
        single_device_manager.resolve_group("Anywhere")
