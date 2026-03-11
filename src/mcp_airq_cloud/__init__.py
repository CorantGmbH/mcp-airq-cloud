"""MCP server for air-Q Cloud API — access air quality data from anywhere."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("mcp-airq-cloud")
except PackageNotFoundError:
    __version__ = "0.0.0"
