"""Device configuration loading from environment variables or config file."""

import json
import logging
import os
import stat
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DeviceConfig:
    """Configuration for a single air-Q Cloud device."""

    id: str
    api_key: str
    name: str
    location: str | None = None
    group: str | None = None


def _warn_if_world_readable(path: str) -> None:
    """Log a warning if the config file is readable by group or others."""
    try:
        mode = os.stat(path).st_mode
        if mode & (stat.S_IRGRP | stat.S_IROTH):
            logger.warning(
                "Config file '%s' is readable by group/others (mode %s). "
                "This file contains API keys. "
                "Run 'chmod 600 %s' to restrict access.",
                path,
                oct(mode),
                path,
            )
    except OSError:
        pass  # file access errors are handled later when opening the file


DEFAULT_CONFIG_FILE = os.path.expanduser("~/.config/airq-cloud-devices.json")


def load_config() -> list[DeviceConfig]:
    """Load device configs from AIRQ_CLOUD_DEVICES env var or AIRQ_CLOUD_CONFIG_FILE.

    AIRQ_CLOUD_DEVICES: JSON array of objects with 'id', optional 'api_key',
    and optional 'name' fields.

    AIRQ_CLOUD_CONFIG_FILE: path to a JSON file with the same structure.
    Falls back to ~/.config/airq-cloud-devices.json if neither env var is set.

    AIRQ_CLOUD_API_KEY: global fallback API key used when a device entry
    does not include its own 'api_key'.

    Raises ValueError if no devices are configured or JSON is malformed.
    """
    raw = os.environ.get("AIRQ_CLOUD_DEVICES")
    if raw is None:
        config_file = os.environ.get("AIRQ_CLOUD_CONFIG_FILE")
        if config_file is None:
            if os.path.exists(DEFAULT_CONFIG_FILE):
                config_file = DEFAULT_CONFIG_FILE
            else:
                raise ValueError(
                    "No air-Q Cloud devices configured. Set AIRQ_CLOUD_DEVICES env var "
                    "(JSON array) or AIRQ_CLOUD_CONFIG_FILE (path to JSON file), "
                    f"or create {DEFAULT_CONFIG_FILE}."
                )
        _warn_if_world_readable(config_file)
        with open(config_file, encoding="utf-8") as f:
            raw = f.read()

    try:
        entries = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in device config: {exc}") from exc

    if not isinstance(entries, list) or len(entries) == 0:
        raise ValueError("Device config must be a non-empty JSON array.")

    global_api_key = os.environ.get("AIRQ_CLOUD_API_KEY")

    devices = []
    for i, entry in enumerate(entries):
        if "id" not in entry:
            raise ValueError(f"Device entry {i} missing required 'id' field.")

        device_id = entry["id"]
        if not isinstance(device_id, str) or len(device_id) != 32:
            raise ValueError(
                f"Device entry {i}: 'id' must be a 32-character string, "
                f"got {len(device_id) if isinstance(device_id, str) else type(device_id).__name__}."
            )

        api_key = entry.get("api_key", global_api_key)
        if not api_key:
            raise ValueError(
                f"Device entry {i} has no 'api_key' and AIRQ_CLOUD_API_KEY is not set. Each device needs an API key."
            )

        devices.append(
            DeviceConfig(
                id=device_id,
                api_key=api_key,
                name=entry.get("name", device_id[:8] + "..."),
                location=entry.get("location"),
                group=entry.get("group"),
            )
        )

    return devices
