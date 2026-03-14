"""Tests for the direct CLI wrapper."""

from unittest.mock import AsyncMock, patch

from mcp.server.fastmcp.utilities.types import Image

from mcp_airq_cloud.cli import main


def test_main_runs_list_devices_command(capsys):
    """A simple read command is executed and printed."""
    with patch("mcp_airq_cloud.cli._invoke_tool", new_callable=AsyncMock, return_value='["Test"]') as mock_invoke:
        result = main(["list-devices"])

    assert result == 0
    mock_invoke.assert_awaited_once_with("list_devices", {})
    captured = capsys.readouterr()
    assert captured.out == '["Test"]\n'


def test_main_parses_list_arguments():
    """List-valued tool parameters are parsed from repeated CLI values."""
    with patch("mcp_airq_cloud.cli._invoke_tool", new_callable=AsyncMock, return_value="ok") as mock_invoke:
        main(
            [
                "get-air-quality-history",
                "--device",
                "Living Room",
                "--last-hours",
                "24",
                "--sensors",
                "co2",
                "pm2_5",
                "--max-points",
                "150",
            ]
        )

    mock_invoke.assert_awaited_once_with(
        "get_air_quality_history",
        {
            "device": "Living Room",
            "last_hours": 24.0,
            "from_datetime": None,
            "to_datetime": None,
            "sensors": ["co2", "pm2_5"],
            "max_points": 150,
        },
    )


def test_main_writes_plot_image(tmp_path, capsys):
    """PNG plots are written to the requested file path."""
    output = tmp_path / "co2.png"
    image = Image(data=b"png-bytes", format="png")

    with patch("mcp_airq_cloud.cli._invoke_tool", new_callable=AsyncMock, return_value=image) as mock_invoke:
        result = main(
            [
                "plot-air-quality-history",
                "--sensor",
                "co2",
                "--device",
                "Living Room",
                "--output",
                str(output),
            ]
        )

    assert result == 0
    mock_invoke.assert_awaited_once_with(
        "plot_air_quality_history",
        {
            "sensor": "co2",
            "device": "Living Room",
            "last_hours": None,
            "from_datetime": None,
            "to_datetime": None,
            "title": None,
            "x_axis_title": None,
            "y_axis_title": None,
            "chart_type": "area",
            "dark": False,
            "output_format": "png",
            "max_points": 300,
        },
    )
    assert output.read_bytes() == b"png-bytes"
    assert capsys.readouterr().out == f"{output}\n"


def test_main_compacts_json_for_pipes(capsys):
    """Structured JSON can be emitted without whitespace."""
    with patch(
        "mcp_airq_cloud.cli._invoke_tool",
        new_callable=AsyncMock,
        return_value='{\n  "count": 2,\n  "columns": {"co2": [700, 800]}\n}',
    ):
        result = main(
            [
                "get-air-quality-history",
                "--device",
                "Living Room",
                "--compact-json",
            ]
        )

    assert result == 0
    assert capsys.readouterr().out == '{"count":2,"columns":{"co2":[700,800]}}\n'


def test_main_can_render_yaml(capsys):
    """Structured JSON can be emitted as YAML."""
    with patch(
        "mcp_airq_cloud.cli._invoke_tool",
        new_callable=AsyncMock,
        return_value='{"count": 2, "columns": {"co2": [700, 800]}}',
    ):
        result = main(["get-air-quality-history", "--device", "Living Room", "--yaml"])

    assert result == 0
    assert capsys.readouterr().out == "count: 2\ncolumns:\n  co2:\n    - 700\n    - 800\n"


def test_main_streams_plot_image_to_stdout_when_requested():
    """Using --output - writes binary plot data to stdout for piping."""
    image = Image(data=b"png-bytes", format="png")

    with (
        patch("mcp_airq_cloud.cli._invoke_tool", new_callable=AsyncMock, return_value=image) as mock_invoke,
        patch("mcp_airq_cloud.cli._write_stdout_bytes") as mock_write_stdout_bytes,
    ):
        result = main(
            [
                "plot-air-quality-history",
                "--sensor",
                "co2",
                "--device",
                "Living Room",
                "--output",
                "-",
            ]
        )

    assert result == 0
    mock_invoke.assert_awaited_once()
    mock_write_stdout_bytes.assert_called_once_with(b"png-bytes")


def test_main_returns_non_zero_for_tool_errors(capsys):
    """Tool error strings are written to stderr with a failure exit code."""
    with patch(
        "mcp_airq_cloud.cli._invoke_tool",
        new_callable=AsyncMock,
        return_value="Configuration error: missing device",
    ) as mock_invoke:
        result = main(["list-devices"])

    assert result == 1
    mock_invoke.assert_awaited_once_with("list_devices", {})
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "Configuration error: missing device\n"
