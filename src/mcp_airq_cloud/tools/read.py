"""Read-only tools for querying air-Q Cloud data."""

import json
from collections.abc import Sequence
from datetime import datetime, timedelta, timezone

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from mcp_airq_cloud.cloud_device import CloudDevice
from mcp_airq_cloud.devices import DeviceManager
from mcp_airq_cloud.errors import handle_cloud_errors
from mcp_airq_cloud.guides import build_sensor_guide
from mcp_airq_cloud.server import mcp

READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False)


def _manager(ctx: Context) -> DeviceManager:
    """Extract DeviceManager from request context."""
    return ctx.request_context.lifespan_context


@mcp.tool(annotations=READ_ONLY)
@handle_cloud_errors
async def list_devices(ctx: Context) -> str:
    """List all configured air-Q Cloud devices with their names, IDs, locations, and groups."""
    mgr = _manager(ctx)
    devices = []
    for name in mgr.device_names:
        cfg = mgr.get_config_for(name)
        entry: dict[str, str] = {"name": name, "id": cfg.id[:8] + "..."}
        if cfg.location is not None:
            entry["location"] = cfg.location
        if cfg.group is not None:
            entry["group"] = cfg.group
        devices.append(entry)
    return json.dumps(devices, indent=2)


@mcp.tool(annotations=READ_ONLY)
@handle_cloud_errors
async def get_air_quality(
    ctx: Context,
    device: str | None = None,
    location: str | None = None,
    group: str | None = None,
) -> str:
    """Get the most recent air quality sensor readings from the air-Q Cloud.

    Specify exactly one of:
    - 'device' — query a single device by name
    - 'location' — query all devices at a given location (e.g. "Wohnzimmer")
    - 'group' — query all devices in a group (e.g. "zu Hause")

    When using 'location' or 'group', the response contains one entry per
    device. The response includes a _sensor_guide field with unit and index
    documentation — read it before interpreting any values.
    """
    mgr = _manager(ctx)

    selectors = [x for x in (device, location, group) if x is not None]
    if len(selectors) > 1:
        return "Specify at most one of 'device', 'location', or 'group'."

    multi_devices: Sequence[tuple[str, CloudDevice]] | None = None
    if location is not None:
        multi_devices = mgr.resolve_location(location)
    elif group is not None:
        multi_devices = mgr.resolve_group(group)

    if multi_devices is not None:
        results: dict[str, object] = {}
        all_keys: set[str] = set()
        for name, cloud in multi_devices:
            data = await cloud.get_latest_data()
            results[name] = data
            all_keys.update(data.keys())
        results["_sensor_guide"] = build_sensor_guide(all_keys)
        return json.dumps(results, indent=2, default=str)

    cloud = mgr.resolve(device)
    data = await cloud.get_latest_data()
    data["_sensor_guide"] = build_sensor_guide(set(data.keys()))
    return json.dumps(data, indent=2, default=str)


@mcp.tool(annotations=READ_ONLY)
@handle_cloud_errors
async def get_air_quality_history(
    ctx: Context,
    device: str | None = None,
    last_hours: float | None = None,
    from_datetime: str | None = None,
    to_datetime: str | None = None,
) -> str:
    """Get historical air quality data from the air-Q Cloud within a time range.

    Time range can be specified in two ways:
    - 'last_hours' — get data from the last N hours (default: 1 hour)
    - 'from_datetime' and 'to_datetime' — ISO 8601 datetime strings
      (e.g. "2026-03-10T14:00:00" or "2026-03-10T14:00:00+01:00")

    If from_datetime is given, it takes precedence over last_hours.
    If to_datetime is omitted, it defaults to now.
    """
    mgr = _manager(ctx)
    cloud = mgr.resolve(device)

    now = datetime.now(timezone.utc)

    if from_datetime is not None:
        from_dt = datetime.fromisoformat(from_datetime)
        if from_dt.tzinfo is None:
            from_dt = from_dt.replace(tzinfo=timezone.utc)
        to_dt = now
        if to_datetime is not None:
            to_dt = datetime.fromisoformat(to_datetime)
            if to_dt.tzinfo is None:
                to_dt = to_dt.replace(tzinfo=timezone.utc)
    else:
        hours = last_hours if last_hours is not None else 1.0
        if hours <= 0:
            return "last_hours must be positive."
        from_dt = now - timedelta(hours=hours)
        to_dt = now

    if from_dt >= to_dt:
        return "from_datetime must be before to_datetime."

    from_ms = int(from_dt.timestamp() * 1000)
    to_ms = int(to_dt.timestamp() * 1000)

    data = await cloud.get_data_timerange(from_ms, to_ms)

    all_keys: set[str] = set()
    for entry in data:
        all_keys.update(entry.keys())

    result: dict[str, object] = {
        "from": from_dt.isoformat(),
        "to": to_dt.isoformat(),
        "count": len(data),
        "data": data,
    }

    guide = build_sensor_guide(all_keys)
    if guide:
        result["_sensor_guide"] = guide

    return json.dumps(result, indent=2, default=str)
