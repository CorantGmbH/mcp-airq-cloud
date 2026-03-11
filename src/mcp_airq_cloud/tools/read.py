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
    - 'device' — query a single device by name (e.g. "Wohnzimmer")
    - 'location' — query all devices at a given location (e.g. "zu Hause")
    - 'group' — query all devices in a group

    Use list_devices first to see valid device names, locations, and groups.
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


def _parse_time_range(
    now: datetime,
    last_hours: float | None,
    from_datetime: str | None,
    to_datetime: str | None,
) -> tuple[datetime, datetime] | str:
    """Parse time range parameters. Returns (from_dt, to_dt) or an error string."""
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
    return from_dt, to_dt


def _filter_sensors(data: list[dict], sensors: list[str]) -> list[dict]:
    """Keep only the requested sensor keys (plus datetime/timestamp) in each entry."""
    keep = {s.lower() for s in sensors} | {"datetime", "timestamp", "deviceid"}
    return [{k: v for k, v in entry.items() if k.lower() in keep} for entry in data]


def _downsample(data: list[dict], max_points: int) -> list[dict]:
    """Evenly downsample a list to at most max_points entries."""
    n = len(data)
    if n <= max_points:
        return data
    step = n / max_points
    return [data[int(i * step)] for i in range(max_points)]


@mcp.tool(annotations=READ_ONLY)
@handle_cloud_errors
async def get_air_quality_history(  # pylint: disable=too-many-arguments, too-many-locals
    ctx: Context,
    device: str | None = None,
    last_hours: float | None = None,
    from_datetime: str | None = None,
    to_datetime: str | None = None,
    sensors: list[str] | None = None,
    max_points: int | None = None,
) -> str:
    """Get historical air quality data from the air-Q Cloud within a time range.

    IMPORTANT — response size: air-Q records every ~2 minutes, so long ranges
    produce large responses (24 h ≈ 720 readings × ~25 sensors). Always use
    'sensors' and 'max_points' when querying more than 1–2 hours to stay within
    response size limits. Example for a 24 h chart: sensors=["pm1","pm2_5","pm10"],
    max_points=150.

    Time range — specify one of:
    - 'last_hours' — data from the last N hours (default: 1 hour)
    - 'from_datetime' / 'to_datetime' — ISO 8601 strings
      (e.g. "2026-03-10T14:00:00" or "2026-03-10T14:00:00+01:00")
      'from_datetime' takes precedence over 'last_hours'.
      'to_datetime' defaults to now.

    Optional filtering:
    - 'sensors' — sensor names to include (e.g. ["pm1", "pm2_5", "pm10"]).
      datetime and timestamp are always kept. Omit to get all sensors.
      Valid sensor names (device-dependent):
        Climate:    temperature, humidity, humidity_abs, dewpt,
                    pressure, pressure_rel
        Gases:      co2, tvoc, tvoc_ionsc, co, no2, so2, o3, h2s, oxygen,
                    n2o, nh3_MR100, no_M250, hcl, hcn, hf, ph3, sih4,
                    br2, cl2_M20, clo2, cs2, f2, c2h4, c2h4o, ch2o_M10,
                    ch4s, ethanol, acid_M100, h2_M1000, h2o2, ash3,
                    ch4_MIPEX, c3h8_MIPEX, r32, r454b, r454c
        Particles:  pm1, pm2_5, pm10, TypPS,
                    cnt0_3, cnt0_5, cnt1, cnt2_5, cnt5, cnt10,
                    pm1_SPS30, pm2_5_SPS30, pm4_SPS30, pm10_SPS30,
                    cnt0_5_SPS30, cnt1_SPS30, cnt2_5_SPS30, cnt4_SPS30,
                    cnt10_SPS30, TypPS_SPS30
        Acoustics:  sound, sound_max
        Radon:      radon
        Indices:    health, performance, mold, virus
        Other:      flow1, flow2, flow3, flow4, wifi
    - 'max_points' — downsample to at most this many evenly spaced points.
    """
    mgr = _manager(ctx)
    cloud = mgr.resolve(device)

    time_range = _parse_time_range(
        datetime.now(timezone.utc), last_hours, from_datetime, to_datetime
    )
    if isinstance(time_range, str):
        return time_range
    from_dt, to_dt = time_range

    from_ms = int(from_dt.timestamp() * 1000)
    to_ms = int(to_dt.timestamp() * 1000)

    data = await cloud.get_data_timerange(from_ms, to_ms)

    if sensors:
        data = _filter_sensors(data, sensors)

    if max_points is not None and max_points > 0:
        data = _downsample(data, max_points)

    result: dict[str, object] = {
        "from": from_dt.isoformat(),
        "to": to_dt.isoformat(),
        "count": len(data),
        "data": data,
    }

    all_keys = set().union(*(entry.keys() for entry in data)) if data else set()
    guide = build_sensor_guide(all_keys)
    if guide:
        result["_sensor_guide"] = guide

    return json.dumps(result, indent=2, default=str)
