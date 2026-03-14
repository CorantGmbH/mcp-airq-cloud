"""Read-only tools for querying air-Q Cloud data."""

import json
from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from typing import Literal

import aiohttp
from airq_mcp_timeseries.models import (
    PlotRequest,
    PlotStyle,
    Selector,
    SeriesPoint,
    SeriesSet,
    TimeSeries,
)
from airq_mcp_timeseries.renderers import render
from airq_mcp_timeseries.services.plot_model import build_plot_model
from mcp.server.fastmcp import Context
from mcp.server.fastmcp.utilities.types import Image
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


def _check_sensors_present(
    data: list[dict],
    sensors: list[str],
) -> str | None:
    """Return an error string if any requested sensors are missing from the data."""
    if not data or not sensors:
        return None
    meta = {"datetime", "timestamp", "deviceid"}
    present = set().union(*(e.keys() for e in data)) - meta
    missing = {s.lower() for s in sensors} - {k.lower() for k in present}
    if missing:
        available = sorted(k for k in present if k.lower() not in meta)
        msg = f"Sensor(s) not available on this device: {', '.join(sorted(missing))}."
        if available:
            msg += f" Available: {', '.join(available)}."
        return msg
    return None


def _downsample(data: list[dict], max_points: int) -> list[dict]:
    """Evenly downsample a list to at most max_points entries."""
    n = len(data)
    if n <= max_points:
        return data
    step = n / max_points
    return [data[int(i * step)] for i in range(max_points)]


def _to_columnar(data: list[dict]) -> dict[str, list]:
    """Convert row-oriented data to column-oriented format.

    Drops ``deviceid`` and ``datetime`` (redundant with ``timestamp``).
    Timestamps are returned in seconds (divided by 1000).
    """
    if not data:
        return {}
    skip = {"deviceid", "datetime"}
    keys = [k for k in data[0] if k not in skip]
    cols: dict[str, list] = {}
    for k in keys:
        if k == "timestamp":
            cols[k] = [row.get(k, 0) // 1000 for row in data]
        else:
            cols[k] = [row.get(k) for row in data]
    return cols


@mcp.tool(annotations=READ_ONLY)
@handle_cloud_errors
async def get_air_quality_history(
    ctx: Context,
    device: str | None = None,
    last_hours: float | None = None,
    from_datetime: str | None = None,
    to_datetime: str | None = None,
    sensors: list[str] | None = None,
    max_points: int | None = None,
) -> str:
    """Get historical air quality data from the air-Q Cloud within a time range.

    IMPORTANT — 'sensors' must be a JSON array, not a plain string.
      Correct:   sensors=["pm1","pm2_5"]
      Wrong:     sensors="pm1"

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
    - 'sensors' — list of sensor names to include (e.g. ["pm1", "pm2_5", "pm10"]).
      Omit to get all sensors.
      Valid sensor names (device-dependent):
        Climate:    temperature, humidity, humidity_abs, dewpt,
                    pressure, pressure_rel
        Gases:      co2, tvoc, tvoc_ionsc, co, no2, so2, o3, h2s, oxygen,
                    n2o, nh3_mr100, no_m250, hcl, hcn, hf, ph3, sih4,
                    br2, cl2_m20, clo2, cs2, f2, c2h4, c2h4o, ch2o_m10,
                    ch4s, ethanol, acid_m100, h2_m1000, h2o2, ash3,
                    ch4_mipex, c3h8_mipex, r32, r454b, r454c
        Particles:  pm1, pm2_5, pm10, typps,
                    cnt0_3, cnt0_5, cnt1, cnt2_5, cnt5, cnt10,
                    pm1_sps30, pm2_5_sps30, pm4_sps30, pm10_sps30,
                    cnt0_5_sps30, cnt1_sps30, cnt2_5_sps30, cnt4_sps30,
                    cnt10_sps30, typps_sps30
        Acoustics:  sound, sound_max
        Radon:      radon
        Indices:    health, performance, mold, virus
        Other:      flow1, flow2, flow3, flow4, wifi
    - 'max_points' — downsample to at most this many evenly spaced points.

    Response: column-oriented JSON. Timestamps are Unix seconds (integer).
    Includes _sensor_guide with unit and interpretation documentation.
    """
    mgr = _manager(ctx)
    cloud = mgr.resolve(device)

    time_range = _parse_time_range(datetime.now(timezone.utc), last_hours, from_datetime, to_datetime)
    if isinstance(time_range, str):
        return time_range
    from_dt, to_dt = time_range

    from_ms = int(from_dt.timestamp() * 1000)
    to_ms = int(to_dt.timestamp() * 1000)

    data = await cloud.get_data_timerange(from_ms, to_ms)

    if sensors:
        error = _check_sensors_present(data, sensors)
        if error:
            return error
        data = _filter_sensors(data, sensors)

    if max_points is not None and max_points > 0:
        data = _downsample(data, max_points)

    all_keys = set().union(*(entry.keys() for entry in data)) if data else set()
    result: dict[str, object] = {
        "from": from_dt.isoformat(),
        "to": to_dt.isoformat(),
        "count": len(data),
        "columns": _to_columnar(data),
    }
    guide = build_sensor_guide(all_keys)
    if guide:
        result["_sensor_guide"] = guide
    return json.dumps(result, separators=(",", ":"), default=str)


def _rows_to_series_set(
    device_label: str,
    sensor: str,
    data: list[dict],
    from_dt: datetime,
    to_dt: datetime,
) -> SeriesSet:
    """Convert raw cloud rows to a SeriesSet for chart rendering."""
    key = sensor.lower()
    points = []
    for row in data:
        ts_ms = row.get("timestamp", 0)
        ts_iso = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).isoformat()
        val_raw = row.get(key)
        if val_raw is None:
            val: float | None = None
        elif isinstance(val_raw, list):
            val = float(val_raw[0]) if val_raw else None
        else:
            try:
                val = float(val_raw)
            except (TypeError, ValueError):
                val = None
        points.append(SeriesPoint(ts=ts_iso, value=val))
    ts = TimeSeries(id=device_label, label=device_label, unit=None, points=points)
    return SeriesSet(
        metric=key,
        series=[ts],
        start=from_dt.isoformat(),
        end=to_dt.isoformat(),
    )


@mcp.tool(annotations=READ_ONLY, structured_output=False)
async def plot_air_quality_history(
    ctx: Context,
    sensor: str,
    device: str | None = None,
    last_hours: float | None = None,
    from_datetime: str | None = None,
    to_datetime: str | None = None,
    title: str | None = None,
    x_axis_title: str | None = None,
    y_axis_title: str | None = None,
    chart_type: Literal["line", "area"] = "area",
    dark: bool = False,
    output_format: Literal["png", "html"] = "png",
    max_points: int = 300,
) -> Image | str:
    """Generate a chart of historical air-Q Cloud sensor data.

    WHEN TO USE THIS TOOL: Call this whenever the user asks to see a graph,
    chart, plot, or visual representation of historical sensor data.

    OUTPUT FORMAT:
    - "png" (default) — returns an inline image; very token-efficient because
      the raw data never appears in the conversation. Use this in almost all cases.
    - "html" — returns a self-contained interactive HTML page (with dark/light
      toggle). Use only when the user explicitly wants an interactive chart or
      a downloadable file for claude.ai Canvas/Artifacts.

    REQUIRED
    - sensor: the sensor key to visualise (one sensor per chart).
      Examples: "co2", "temperature", "humidity", "pm2_5", "tvoc",
                "pressure", "sound", "radon", "health", "virus"
      Only one sensor can be shown per chart. Call the tool multiple times
      to produce charts for several sensors.

    AXIS LABELS — always set these in the user's current language.
    The LLM is responsible for choosing correct labels and units because
    sensor labels and user languages are known only at call time.
    - title: headline shown above the chart
        German:  "CO₂-Verlauf Wohnzimmer (letzte 24 h)"
        English: "CO₂ Trend Living Room (last 24 h)"
        French:  "Évolution CO₂ Salon (24 dernières h)"
    - y_axis_title: value-axis label including the unit
        "CO₂ (ppm)"  |  "Temperatur (°C)"  |  "PM2.5 (µg/m³)"
        "Humidity (%)"  |  "Sound (dB(A))"  |  "Radon (Bq/m³)"
    - x_axis_title: time-axis label (optional, leave None to omit)
        "Zeit"  |  "Time"  |  "Temps"

    TIME RANGE — specify exactly one of:
    - last_hours: data from the last N hours (default: 24)
    - from_datetime / to_datetime: ISO 8601 strings
      (e.g. "2026-03-10T14:00:00" or "2026-03-10T14:00:00+01:00")
      'from_datetime' takes precedence over 'last_hours'.
      'to_datetime' defaults to now.

    DEVICE — optional when only one device is configured.
    Use list_devices to obtain valid names.

    STYLE OPTIONS:
    - chart_type: "area" (default, filled under the curve) or "line"
    - dark: True for dark background (default: False / light)
    - max_points: maximum data points to render (default: 300). For time
      ranges longer than 4 hours keep this at 300 or lower.
    """
    try:
        mgr = _manager(ctx)

        names = mgr.device_names
        if device is None and len(names) == 1:
            device_label = names[0]
        elif device is not None:
            device_label = device
        else:
            return f"Multiple devices configured. Specify one of: {', '.join(names)}"

        cloud = mgr.resolve(device)

        effective_hours = last_hours if last_hours is not None else 24.0
        time_range = _parse_time_range(datetime.now(timezone.utc), effective_hours, from_datetime, to_datetime)
        if isinstance(time_range, str):
            return time_range
        from_dt, to_dt = time_range

        from_ms = int(from_dt.timestamp() * 1000)
        to_ms = int(to_dt.timestamp() * 1000)
        data = await cloud.get_data_timerange(from_ms, to_ms)

        key = sensor.lower()
        error = _check_sensors_present(data, [key])
        if error:
            return error

        if max_points > 0:
            data = _downsample(data, max_points)

        series_set = _rows_to_series_set(device_label, key, data, from_dt, to_dt)

        request = PlotRequest(
            selector=Selector(devices=[device_label]),
            metric=key,
            start=from_dt,
            end=to_dt,
            chart_type=chart_type,
            output_format=output_format,
            style=PlotStyle(
                title=title,
                x_axis_title=x_axis_title,
                y_axis_title=y_axis_title,
                dark=dark,
            ),
        )

        model = build_plot_model(series_set, request)
        result = await render(model, request)

        if output_format == "png":
            return Image(data=result.payload, format="png")  # type: ignore[arg-type]
        return result.payload  # type: ignore[return-value]

    except ValueError as exc:
        return f"Configuration error: {exc}"
    except aiohttp.ClientResponseError as exc:
        if exc.status == 401:
            return "Authentication failed. Check the API key."
        return f"Cloud API error (HTTP {exc.status}): {exc.message}"
    except aiohttp.ClientError as exc:
        return f"Network error: {type(exc).__name__}: {exc}"
    except TimeoutError:
        return "Request timed out. Check your internet connection."
    except Exception as exc:  # pylint: disable=broad-except
        return f"Chart rendering failed: {exc}"
