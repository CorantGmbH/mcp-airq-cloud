"""Device manager: maintains CloudDevice instances and resolves device names."""

import aiohttp

from mcp_airq_cloud.cloud_device import CloudDevice
from mcp_airq_cloud.config import DeviceConfig


class DeviceManager:
    """Holds the shared aiohttp session and creates CloudDevice instances on demand."""

    def __init__(self, session: aiohttp.ClientSession, configs: list[DeviceConfig]) -> None:
        self._session = session
        self._configs = {cfg.name: cfg for cfg in configs}
        self._instances: dict[str, CloudDevice] = {}

    @property
    def device_names(self) -> list[str]:
        """Return all configured device names."""
        return list(self._configs.keys())

    def _unique_values(self, field: str) -> list[str]:
        """Return unique non-None values of a DeviceConfig field, insertion-ordered."""
        seen: dict[str, None] = {}
        for cfg in self._configs.values():
            value = getattr(cfg, field)
            if value is not None and value not in seen:
                seen[value] = None
        return list(seen)

    def _resolve_by(self, field: str, value: str) -> list[tuple[str, CloudDevice]]:
        """Return all devices whose `field` matches value (case-insensitive substring).

        Raises ValueError if no devices match.
        """
        needle = value.lower()
        matches = [
            name
            for name, cfg in self._configs.items()
            if getattr(cfg, field) is not None and needle in getattr(cfg, field).lower()
        ]
        if not matches:
            available = self._unique_values(field)
            if available:
                raise ValueError(f"No devices with {field}='{value}'. Available: {', '.join(available)}")
            raise ValueError(f"No {field}s configured. Add '{field}' to your device config.")
        return [(name, self._get_or_create(name)) for name in matches]

    @property
    def locations(self) -> list[str]:
        """Return all unique configured locations (excluding devices without one)."""
        return self._unique_values("location")

    @property
    def groups(self) -> list[str]:
        """Return all unique configured groups (excluding devices without one)."""
        return self._unique_values("group")

    def resolve(self, device: str | None) -> CloudDevice:
        """Resolve a device name to a CloudDevice instance.

        If device is None and exactly one device is configured, use that one.
        Otherwise match by case-insensitive substring.
        Raises ValueError on ambiguity or no match.
        """
        if device is None:
            if len(self._configs) == 1:
                device = next(iter(self._configs))
            else:
                raise ValueError(f"Multiple devices configured. Specify one of: {', '.join(self._configs.keys())}")

        assert device is not None  # guaranteed by the block above

        # Exact match first
        if device in self._configs:
            return self._get_or_create(device)

        # Case-insensitive substring match
        needle = device.lower()
        matches = [name for name in self._configs if needle in name.lower()]
        if len(matches) == 1:
            return self._get_or_create(matches[0])
        if len(matches) == 0:
            raise ValueError(f"No device matching '{device}'. Available: {', '.join(self._configs.keys())}")
        raise ValueError(f"Ambiguous device '{device}'. Matches: {', '.join(matches)}")

    def resolve_location(self, location: str) -> list[tuple[str, CloudDevice]]:
        """Resolve a location string to all devices at that location.

        Uses case-insensitive substring matching.
        Raises ValueError if no devices match.
        """
        return self._resolve_by("location", location)

    def resolve_group(self, group: str) -> list[tuple[str, CloudDevice]]:
        """Resolve a group string to all devices in that group.

        Uses case-insensitive substring matching.
        Raises ValueError if no devices match.
        """
        return self._resolve_by("group", group)

    def get_config_for(self, device_name: str) -> DeviceConfig:
        """Return the DeviceConfig for a resolved device name."""
        return self._configs[device_name]

    def _get_or_create(self, name: str) -> CloudDevice:
        """Get cached CloudDevice instance or create one."""
        if name not in self._instances:
            cfg = self._configs[name]
            self._instances[name] = CloudDevice(cfg.id, cfg.api_key, self._session)
        return self._instances[name]
