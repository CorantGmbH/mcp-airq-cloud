"""Tests for package __init__ and prompts."""

import importlib
from importlib.metadata import PackageNotFoundError
from unittest.mock import patch

import mcp_airq_cloud
from mcp_airq_cloud.prompts import airq_sensor_guide


def test_version_fallback():
    """When package metadata is unavailable, __version__ defaults to '0.0.0'."""
    with patch("importlib.metadata.version", side_effect=PackageNotFoundError):
        importlib.reload(mcp_airq_cloud)
        assert mcp_airq_cloud.__version__ == "0.0.0"


def test_prompts_return_strings():
    """Sensor guide prompt returns a non-empty string."""
    assert isinstance(airq_sensor_guide(), str)
    assert len(airq_sensor_guide()) > 0


def test_build_sensor_guide_no_matching_keys():
    """build_sensor_guide returns empty string when no sensor keys match."""
    from mcp_airq_cloud.guides import build_sensor_guide

    result = build_sensor_guide({"unknown_sensor_xyz"})
    assert result == ""
