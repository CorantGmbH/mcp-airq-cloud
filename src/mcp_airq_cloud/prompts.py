"""MCP prompt registrations for air-Q Cloud."""

from mcp_airq_cloud.guides import SENSOR_GUIDE
from mcp_airq_cloud.server import mcp


@mcp.prompt()
def airq_sensor_guide() -> str:
    """Guide for interpreting air-Q sensor values: units, ranges, and semantics."""
    return SENSOR_GUIDE
