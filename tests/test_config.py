"""Tests for config loading."""

import json
import pytest

from mcp_airq_cloud.config import DeviceConfig, load_config

DEVICE_ID = "a" * 32


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Ensure no leftover env vars."""
    monkeypatch.delenv("AIRQ_CLOUD_DEVICES", raising=False)
    monkeypatch.delenv("AIRQ_CLOUD_CONFIG_FILE", raising=False)
    monkeypatch.delenv("AIRQ_CLOUD_API_KEY", raising=False)


def test_load_from_env_single_device(monkeypatch):
    """Load a single device from AIRQ_CLOUD_DEVICES."""
    devices_json = json.dumps(
        [{"id": DEVICE_ID, "api_key": "key123", "name": "MyAirQ"}]
    )
    monkeypatch.setenv("AIRQ_CLOUD_DEVICES", devices_json)
    configs = load_config()
    assert len(configs) == 1
    assert configs[0] == DeviceConfig(DEVICE_ID, "key123", "MyAirQ")


def test_load_from_env_multiple_devices(monkeypatch):
    """Load multiple devices from AIRQ_CLOUD_DEVICES."""
    devices_json = json.dumps(
        [
            {"id": "a" * 32, "api_key": "k1", "name": "A"},
            {"id": "b" * 32, "api_key": "k2", "name": "B"},
        ]
    )
    monkeypatch.setenv("AIRQ_CLOUD_DEVICES", devices_json)
    configs = load_config()
    assert len(configs) == 2


def test_name_defaults_to_truncated_id(monkeypatch):
    """If name is omitted, default to first 8 chars of ID + '...'."""
    devices_json = json.dumps([{"id": DEVICE_ID, "api_key": "key"}])
    monkeypatch.setenv("AIRQ_CLOUD_DEVICES", devices_json)
    configs = load_config()
    assert configs[0].name == DEVICE_ID[:8] + "..."


def test_api_key_from_global_env(monkeypatch):
    """Fall back to AIRQ_CLOUD_API_KEY when per-device key is missing."""
    devices_json = json.dumps([{"id": DEVICE_ID, "name": "Test"}])
    monkeypatch.setenv("AIRQ_CLOUD_DEVICES", devices_json)
    monkeypatch.setenv("AIRQ_CLOUD_API_KEY", "global_key")
    configs = load_config()
    assert configs[0].api_key == "global_key"


def test_per_device_key_overrides_global(monkeypatch):
    """Per-device api_key takes precedence over global key."""
    devices_json = json.dumps(
        [{"id": DEVICE_ID, "api_key": "device_key", "name": "Test"}]
    )
    monkeypatch.setenv("AIRQ_CLOUD_DEVICES", devices_json)
    monkeypatch.setenv("AIRQ_CLOUD_API_KEY", "global_key")
    configs = load_config()
    assert configs[0].api_key == "device_key"


def test_no_api_key_anywhere_raises(monkeypatch):
    """Raise ValueError when neither per-device nor global API key is set."""
    devices_json = json.dumps([{"id": DEVICE_ID, "name": "Test"}])
    monkeypatch.setenv("AIRQ_CLOUD_DEVICES", devices_json)
    with pytest.raises(ValueError, match="api_key"):
        load_config()


def test_location_is_optional(monkeypatch):
    """Location defaults to None when omitted."""
    devices_json = json.dumps([{"id": DEVICE_ID, "api_key": "key"}])
    monkeypatch.setenv("AIRQ_CLOUD_DEVICES", devices_json)
    configs = load_config()
    assert configs[0].location is None


def test_location_is_loaded(monkeypatch):
    """Location is parsed from config."""
    devices_json = json.dumps(
        [{"id": DEVICE_ID, "api_key": "key", "location": "Wohnzimmer"}]
    )
    monkeypatch.setenv("AIRQ_CLOUD_DEVICES", devices_json)
    configs = load_config()
    assert configs[0].location == "Wohnzimmer"


def test_group_is_optional(monkeypatch):
    """Group defaults to None when omitted."""
    devices_json = json.dumps([{"id": DEVICE_ID, "api_key": "key"}])
    monkeypatch.setenv("AIRQ_CLOUD_DEVICES", devices_json)
    configs = load_config()
    assert configs[0].group is None


def test_group_is_loaded(monkeypatch):
    """Group is parsed from config."""
    devices_json = json.dumps(
        [{"id": DEVICE_ID, "api_key": "key", "group": "zu Hause"}]
    )
    monkeypatch.setenv("AIRQ_CLOUD_DEVICES", devices_json)
    configs = load_config()
    assert configs[0].group == "zu Hause"


def test_load_from_file(monkeypatch, tmp_path):
    """Load from AIRQ_CLOUD_CONFIG_FILE."""
    config_file = tmp_path / "devices.json"
    config_file.write_text(
        json.dumps([{"id": DEVICE_ID, "api_key": "fkey", "name": "File"}])
    )
    monkeypatch.setenv("AIRQ_CLOUD_CONFIG_FILE", str(config_file))
    configs = load_config()
    assert configs[0].name == "File"


def test_no_config_raises():
    """Raise ValueError when no config is set."""
    with pytest.raises(ValueError, match="No air-Q Cloud devices configured"):
        load_config()


def test_invalid_json_raises(monkeypatch):
    """Raise ValueError for malformed JSON."""
    monkeypatch.setenv("AIRQ_CLOUD_DEVICES", "not json")
    with pytest.raises(ValueError, match="Invalid JSON"):
        load_config()


def test_empty_array_raises(monkeypatch):
    """Raise ValueError for empty device list."""
    monkeypatch.setenv("AIRQ_CLOUD_DEVICES", "[]")
    with pytest.raises(ValueError, match="non-empty"):
        load_config()


def test_missing_id_raises(monkeypatch):
    """Raise ValueError when id is missing."""
    monkeypatch.setenv("AIRQ_CLOUD_DEVICES", json.dumps([{"api_key": "key"}]))
    with pytest.raises(ValueError, match="missing required 'id'"):
        load_config()


def test_invalid_id_length_raises(monkeypatch):
    """Raise ValueError when id is not 32 characters."""
    monkeypatch.setenv(
        "AIRQ_CLOUD_DEVICES", json.dumps([{"id": "short", "api_key": "key"}])
    )
    with pytest.raises(ValueError, match="32-character"):
        load_config()


def test_file_permissions_warning(monkeypatch, tmp_path, caplog):
    """Warn when config file is world-readable."""
    config_file = tmp_path / "devices.json"
    config_file.write_text(
        json.dumps([{"id": DEVICE_ID, "api_key": "key", "name": "Test"}])
    )
    config_file.chmod(0o644)
    monkeypatch.setenv("AIRQ_CLOUD_CONFIG_FILE", str(config_file))
    with caplog.at_level("WARNING"):
        load_config()
    assert "readable by group/others" in caplog.text


def test_file_permissions_oserror_is_ignored(monkeypatch, tmp_path):
    """OSError during permission check is silently ignored."""
    from unittest.mock import patch

    config_file = tmp_path / "devices.json"
    config_file.write_text(
        json.dumps([{"id": DEVICE_ID, "api_key": "key", "name": "Test"}])
    )
    monkeypatch.setenv("AIRQ_CLOUD_CONFIG_FILE", str(config_file))
    with patch("os.stat", side_effect=OSError("permission denied")):
        configs = load_config()
    assert configs[0].name == "Test"
