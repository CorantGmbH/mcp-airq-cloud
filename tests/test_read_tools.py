"""Tests for read-only tools."""

import base64
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp.server.fastmcp.utilities.types import Image
from mcp.types import BlobResourceContents, EmbeddedResource, TextResourceContents
from airq_mcp_timeseries.models import PlotResult

from mcp_airq_cloud.config import DeviceConfig
from mcp_airq_cloud.devices import DeviceManager
from mcp_airq_cloud.tools.read import (
    export_air_quality_history,
    get_air_quality,
    get_air_quality_history,
    list_devices,
    plot_air_quality_history,
)

DEVICE_ID = "a" * 32


@pytest.fixture
def mock_ctx(single_device_manager):
    """Create a mock Context with the device manager as lifespan context."""
    ctx = MagicMock()
    ctx.request_context.lifespan_context = single_device_manager
    return ctx


@pytest.fixture
def mock_cloud_device():
    """Create a mock CloudDevice instance."""
    cloud = AsyncMock()
    cloud.get_latest_data.return_value = {
        "temperature": 22.5,
        "humidity": 45.0,
        "co2": 410,
        "status": "OK",
    }
    cloud.get_data_timerange.return_value = [
        {"temperature": 22.0, "co2": 400, "timestamp": 1000},
        {"temperature": 23.0, "co2": 420, "timestamp": 2000},
    ]
    return cloud


async def test_list_devices(mock_ctx):
    """list_devices returns configured devices."""
    result = await list_devices(mock_ctx)
    data = json.loads(result)
    assert len(data) == 1
    assert data[0]["name"] == "TestDevice"
    assert data[0]["id"] == DEVICE_ID[:8] + "..."
    assert "location" not in data[0]
    assert "group" not in data[0]


async def test_list_devices_with_location(mock_session):
    """list_devices includes location when configured."""
    configs = [DeviceConfig(DEVICE_ID, "key", "MyAirQ", location="Wohnzimmer")]
    mgr = DeviceManager(mock_session, configs)
    ctx = MagicMock()
    ctx.request_context.lifespan_context = mgr
    result = await list_devices(ctx)
    data = json.loads(result)
    assert data[0]["location"] == "Wohnzimmer"


async def test_list_devices_with_group(mock_session):
    """list_devices includes group when configured."""
    configs = [DeviceConfig(DEVICE_ID, "key", "MyAirQ", group="zu Hause")]
    mgr = DeviceManager(mock_session, configs)
    ctx = MagicMock()
    ctx.request_context.lifespan_context = mgr
    result = await list_devices(ctx)
    data = json.loads(result)
    assert data[0]["group"] == "zu Hause"


async def test_get_air_quality(mock_ctx, mock_cloud_device):
    """get_air_quality returns sensor data."""
    with patch.object(
        mock_ctx.request_context.lifespan_context,
        "resolve",
        return_value=mock_cloud_device,
    ):
        result = await get_air_quality(mock_ctx)
        data = json.loads(result)
        assert data["temperature"] == 22.5
        assert data["co2"] == 410
        mock_cloud_device.get_latest_data.assert_awaited_once()


async def test_get_air_quality_includes_sensor_guide(mock_ctx, mock_cloud_device):
    """get_air_quality includes a _sensor_guide field."""
    with patch.object(
        mock_ctx.request_context.lifespan_context,
        "resolve",
        return_value=mock_cloud_device,
    ):
        result = await get_air_quality(mock_ctx)
        data = json.loads(result)
        assert "_sensor_guide" in data
        assert "temperature" in data["_sensor_guide"]


async def test_get_air_quality_by_location(mock_session):
    """get_air_quality with location queries all devices at that location."""
    configs = [
        DeviceConfig("a" * 32, "k1", "air-Q Basic", location="Wohnzimmer"),
        DeviceConfig("b" * 32, "k2", "air-Q Radon", location="Wohnzimmer"),
    ]
    mgr = DeviceManager(mock_session, configs)
    ctx = MagicMock()
    ctx.request_context.lifespan_context = mgr

    mock_cloud_1 = AsyncMock()
    mock_cloud_1.get_latest_data.return_value = {"temperature": 22.0, "co2": 400}
    mock_cloud_2 = AsyncMock()
    mock_cloud_2.get_latest_data.return_value = {"temperature": 22.5, "radon": 50}

    with patch.object(
        mgr,
        "resolve_location",
        return_value=[
            ("air-Q Basic", mock_cloud_1),
            ("air-Q Radon", mock_cloud_2),
        ],
    ):
        result = await get_air_quality(ctx, location="Wohnzimmer")
        data = json.loads(result)
        assert "air-Q Basic" in data
        assert "air-Q Radon" in data
        assert data["air-Q Basic"]["temperature"] == 22.0


async def test_get_air_quality_by_group(mock_session):
    """get_air_quality with group queries all devices in that group."""
    configs = [
        DeviceConfig("a" * 32, "k1", "Wohnzimmer", group="zu Hause"),
        DeviceConfig("b" * 32, "k2", "Schlafzimmer", group="zu Hause"),
    ]
    mgr = DeviceManager(mock_session, configs)
    ctx = MagicMock()
    ctx.request_context.lifespan_context = mgr

    mock_cloud_1 = AsyncMock()
    mock_cloud_1.get_latest_data.return_value = {"temperature": 22.0}
    mock_cloud_2 = AsyncMock()
    mock_cloud_2.get_latest_data.return_value = {"temperature": 19.5}

    with patch.object(
        mgr,
        "resolve_group",
        return_value=[
            ("Wohnzimmer", mock_cloud_1),
            ("Schlafzimmer", mock_cloud_2),
        ],
    ):
        result = await get_air_quality(ctx, group="zu Hause")
        data = json.loads(result)
        assert "Wohnzimmer" in data
        assert "Schlafzimmer" in data


async def test_get_air_quality_multiple_selectors_rejected(mock_ctx):
    """get_air_quality rejects more than one selector."""
    result = await get_air_quality(mock_ctx, device="foo", location="bar")
    assert "at most one" in result


async def test_get_air_quality_history_default_last_hour(mock_ctx, mock_cloud_device):
    """get_air_quality_history defaults to last 1 hour."""
    with patch.object(
        mock_ctx.request_context.lifespan_context,
        "resolve",
        return_value=mock_cloud_device,
    ):
        result = await get_air_quality_history(mock_ctx)
        data = json.loads(result)
        assert data["count"] == 2
        assert "columns" in data
        mock_cloud_device.get_data_timerange.assert_awaited_once()


async def test_get_air_quality_history_custom_hours(mock_ctx, mock_cloud_device):
    """get_air_quality_history accepts custom last_hours."""
    with patch.object(
        mock_ctx.request_context.lifespan_context,
        "resolve",
        return_value=mock_cloud_device,
    ):
        result = await get_air_quality_history(mock_ctx, last_hours=6.0)
        data = json.loads(result)
        assert data["count"] == 2


async def test_get_air_quality_history_from_to(mock_ctx, mock_cloud_device):
    """get_air_quality_history accepts from_datetime and to_datetime."""
    with patch.object(
        mock_ctx.request_context.lifespan_context,
        "resolve",
        return_value=mock_cloud_device,
    ):
        result = await get_air_quality_history(
            mock_ctx,
            from_datetime="2026-03-10T14:00:00+00:00",
            to_datetime="2026-03-10T15:00:00+00:00",
        )
        data = json.loads(result)
        assert data["count"] == 2
        assert "2026-03-10" in data["from"]


async def test_get_air_quality_history_from_only(mock_ctx, mock_cloud_device):
    """get_air_quality_history defaults to_datetime to now when only from is given."""
    with patch.object(
        mock_ctx.request_context.lifespan_context,
        "resolve",
        return_value=mock_cloud_device,
    ):
        result = await get_air_quality_history(mock_ctx, from_datetime="2026-03-10T14:00:00")
        data = json.loads(result)
        assert data["count"] == 2


async def test_get_air_quality_history_negative_hours(mock_ctx):
    """get_air_quality_history rejects non-positive last_hours."""
    result = await get_air_quality_history(mock_ctx, last_hours=-1)
    assert "positive" in result


async def test_get_air_quality_history_includes_sensor_guide(mock_ctx, mock_cloud_device):
    """get_air_quality_history includes a _sensor_guide field."""
    with patch.object(
        mock_ctx.request_context.lifespan_context,
        "resolve",
        return_value=mock_cloud_device,
    ):
        result = await get_air_quality_history(mock_ctx)
        data = json.loads(result)
        assert "_sensor_guide" in data


async def test_get_air_quality_history_naive_to_datetime(mock_ctx, mock_cloud_device):
    """get_air_quality_history attaches UTC timezone to a naive to_datetime."""
    with patch.object(
        mock_ctx.request_context.lifespan_context,
        "resolve",
        return_value=mock_cloud_device,
    ):
        result = await get_air_quality_history(
            mock_ctx,
            from_datetime="2026-03-10T12:00:00+00:00",
            to_datetime="2026-03-10T15:00:00",  # naive — no timezone
        )
        data = json.loads(result)
        assert data["count"] == 2


async def test_get_air_quality_history_from_after_to(mock_ctx):
    """get_air_quality_history rejects from_datetime >= to_datetime."""
    result = await get_air_quality_history(
        mock_ctx,
        from_datetime="2026-03-10T16:00:00+00:00",
        to_datetime="2026-03-10T15:00:00+00:00",
    )
    assert "before" in result


async def test_get_air_quality_history_sensors_filter(mock_ctx, mock_cloud_device):
    """get_air_quality_history filters to requested sensors only."""
    mock_cloud_device.get_data_timerange.return_value = [
        {"temperature": 22.0, "co2": 400, "pm2_5": 3.1, "timestamp": 1000},
        {"temperature": 23.0, "co2": 420, "pm2_5": 2.8, "timestamp": 2000},
    ]
    with patch.object(
        mock_ctx.request_context.lifespan_context,
        "resolve",
        return_value=mock_cloud_device,
    ):
        result = await get_air_quality_history(mock_ctx, sensors=["pm2_5"])
        data = json.loads(result)
        cols = data["columns"]
        assert "pm2_5" in cols
        assert "timestamp" in cols
        assert "temperature" not in cols
        assert "co2" not in cols


async def test_get_air_quality_history_sensors_case_insensitive(mock_ctx, mock_cloud_device):
    """get_air_quality_history sensor filter is case-insensitive."""
    mock_cloud_device.get_data_timerange.return_value = [
        {"co2": 400, "temperature": 22.0, "timestamp": 1000},
    ]
    with patch.object(
        mock_ctx.request_context.lifespan_context,
        "resolve",
        return_value=mock_cloud_device,
    ):
        result = await get_air_quality_history(mock_ctx, sensors=["CO2"])
        data = json.loads(result)
        cols = data["columns"]
        assert "co2" in cols
        assert "temperature" not in cols


async def test_get_air_quality_history_max_points(mock_ctx, mock_cloud_device):
    """get_air_quality_history downsamples to max_points."""
    mock_cloud_device.get_data_timerange.return_value = [
        {"temperature": 20.0 + i * 0.1, "timestamp": 1000 + i * 1000} for i in range(100)
    ]
    with patch.object(
        mock_ctx.request_context.lifespan_context,
        "resolve",
        return_value=mock_cloud_device,
    ):
        result = await get_air_quality_history(mock_ctx, max_points=10)
        data = json.loads(result)
        assert data["count"] == 10
        assert len(data["columns"]["temperature"]) == 10


async def test_get_air_quality_history_max_points_no_effect_when_fewer(mock_ctx, mock_cloud_device):
    """get_air_quality_history does not upsample when fewer points than max_points."""
    with patch.object(
        mock_ctx.request_context.lifespan_context,
        "resolve",
        return_value=mock_cloud_device,
    ):
        result = await get_air_quality_history(mock_ctx, max_points=100)
        data = json.loads(result)
        assert data["count"] == 2  # original 2 readings


async def test_get_air_quality_history_sensors_and_max_points_combined(mock_ctx, mock_cloud_device):
    """get_air_quality_history applies both sensors filter and max_points."""
    mock_cloud_device.get_data_timerange.return_value = [
        {"temperature": 20.0 + i, "pm10": float(i), "timestamp": 1000 + i * 1000} for i in range(50)
    ]
    with patch.object(
        mock_ctx.request_context.lifespan_context,
        "resolve",
        return_value=mock_cloud_device,
    ):
        result = await get_air_quality_history(mock_ctx, sensors=["pm10"], max_points=5)
        data = json.loads(result)
        assert data["count"] == 5
        cols = data["columns"]
        assert "pm10" in cols
        assert "timestamp" in cols
        assert "temperature" not in cols


async def test_get_air_quality_history_adds_timezone_and_history_guide(mock_ctx, mock_cloud_device):
    """Historical output includes localized timestamps and metadata guidance."""
    with patch.object(
        mock_ctx.request_context.lifespan_context,
        "resolve",
        return_value=mock_cloud_device,
    ):
        result = await get_air_quality_history(
            mock_ctx,
            from_datetime="2026-03-10T14:00:00",
            to_datetime="2026-03-10T15:00:00",
            timezone_name="Europe/Berlin",
        )
        data = json.loads(result)
        assert data["timezone"] == "Europe/Berlin"
        assert data["columns"]["datetime"][0].endswith("+01:00")
        assert "_history_guide" in data


async def test_get_air_quality_history_splits_compound_values(mock_ctx, mock_cloud_device):
    """Compound sensor values are split into value and quality columns."""
    mock_cloud_device.get_data_timerange.return_value = [
        {"co2": [400.5, 97.0], "timestamp": 1000},
        {"co2": [420.0, 95.0], "timestamp": 2000},
    ]
    with patch.object(
        mock_ctx.request_context.lifespan_context,
        "resolve",
        return_value=mock_cloud_device,
    ):
        result = await get_air_quality_history(mock_ctx, sensors=["co2"])
        data = json.loads(result)
        cols = data["columns"]
        assert cols["co2"] == [400.5, 420.0]
        assert cols["co2_quality"] == [97.0, 95.0]


async def test_export_air_quality_history_returns_csv_resource(mock_ctx, mock_cloud_device):
    """CSV export is returned as an embedded resource."""
    with patch.object(
        mock_ctx.request_context.lifespan_context,
        "resolve",
        return_value=mock_cloud_device,
    ):
        result = await export_air_quality_history(mock_ctx, sensor="co2", output_format="csv")
        assert isinstance(result, EmbeddedResource)
        assert isinstance(result.resource, TextResourceContents)
        assert result.resource.mimeType == "text/csv; charset=utf-8"
        lines = result.resource.text.strip().splitlines()
        assert lines[0].startswith("timestamp,")
        assert lines[1].endswith(",400.0")


async def test_export_air_quality_history_returns_xlsx_resource(mock_ctx, mock_cloud_device):
    """Excel export is returned as an embedded binary resource."""
    with patch.object(
        mock_ctx.request_context.lifespan_context,
        "resolve",
        return_value=mock_cloud_device,
    ):
        result = await export_air_quality_history(mock_ctx, sensor="co2", output_format="xlsx")
        assert isinstance(result, EmbeddedResource)
        assert isinstance(result.resource, BlobResourceContents)
        assert result.resource.mimeType == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        payload = base64.b64decode(result.resource.blob)
        assert payload[:2] == b"PK"


async def test_export_air_quality_history_combines_all_devices_into_one_csv_resource(mock_session, multi_device_configs):
    """Export combines all matching cloud devices into one CSV artifact."""
    mgr = DeviceManager(mock_session, multi_device_configs)
    ctx = MagicMock()
    ctx.request_context.lifespan_context = mgr

    living_room = AsyncMock()
    living_room.get_data_timerange.return_value = [{"timestamp": 1000, "co2": 400}]
    office = AsyncMock()
    office.get_data_timerange.return_value = None
    bedroom = AsyncMock()
    bedroom.get_data_timerange.return_value = [{"timestamp": 2000, "co2": 420}]

    with patch.object(
        mgr,
        "all_devices",
        return_value=[("Living Room", living_room), ("Office", office), ("Bedroom", bedroom)],
    ):
        result = await export_air_quality_history(ctx, sensor="co2", output_format="csv")

    assert isinstance(result, EmbeddedResource)
    assert isinstance(result.resource, TextResourceContents)
    assert str(result.resource.uri).endswith("history-all-devices-co2.csv")
    assert "Living Room,co2,ppm,400.0" in result.resource.text
    assert "Bedroom,co2,ppm,420.0" in result.resource.text
    assert "Office" not in result.resource.text


async def test_plot_air_quality_history_supports_svg_resource(mock_ctx, mock_cloud_device):
    """SVG plot output is returned as an embedded resource."""
    with patch.object(
        mock_ctx.request_context.lifespan_context,
        "resolve",
        return_value=mock_cloud_device,
    ):
        result = await plot_air_quality_history(mock_ctx, sensor="co2", output_format="svg")
        assert isinstance(result, EmbeddedResource)
        assert isinstance(result.resource, BlobResourceContents)
        assert result.resource.mimeType == "image/svg+xml"
        payload = base64.b64decode(result.resource.blob)
        assert payload.lstrip().startswith(b"<?xml")


async def test_plot_air_quality_history_combines_all_devices_into_one_resource(mock_session, multi_device_configs):
    """Plot combines all matching cloud devices into one multi-series chart."""
    mgr = DeviceManager(mock_session, multi_device_configs)
    ctx = MagicMock()
    ctx.request_context.lifespan_context = mgr

    living_room = AsyncMock()
    living_room.get_data_timerange.return_value = [{"timestamp": 1000, "co2": 400}]
    office = AsyncMock()
    office.get_data_timerange.return_value = [{"timestamp": 1000, "pm2_5": 12}]
    bedroom = AsyncMock()
    bedroom.get_data_timerange.return_value = [{"timestamp": 2000, "co2": 420}]
    render_result = PlotResult(output_format="svg", mime_type="image/svg+xml", payload=b"<svg/>")

    with patch.object(
        mgr,
        "all_devices",
        return_value=[("Living Room", living_room), ("Office", office), ("Bedroom", bedroom)],
    ), patch("mcp_airq_cloud.tools.read.render", new=AsyncMock(return_value=render_result)) as render_mock:
        result = await plot_air_quality_history(ctx, sensor="co2", output_format="svg")

    assert isinstance(result, EmbeddedResource)
    assert isinstance(result.resource, BlobResourceContents)
    assert str(result.resource.uri).endswith("plot-all-devices-co2.svg")
    assert render_mock.await_args is not None
    model, request = render_mock.await_args.args
    assert [series.label for series in model.series] == ["Living Room", "Bedroom"]
    assert model.y_axis_title == "ppm"
    assert request.selector.devices == ["Living Room", "Bedroom"]


async def test_plot_air_quality_history_supports_webp_image(mock_ctx, mock_cloud_device):
    """WebP plot output is returned as an inline image."""
    with patch.object(
        mock_ctx.request_context.lifespan_context,
        "resolve",
        return_value=mock_cloud_device,
    ):
        result = await plot_air_quality_history(mock_ctx, sensor="co2", output_format="webp")
        assert isinstance(result, Image)
