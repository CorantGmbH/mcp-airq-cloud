"""MCP server for air-Q Cloud API — access air quality data from anywhere."""

import logging
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import aiohttp
from mcp.server.fastmcp import FastMCP

from mcp_airq_cloud import __version__
from mcp_airq_cloud.config import load_config
from mcp_airq_cloud.devices import DeviceManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("mcp-airq-cloud")


@asynccontextmanager
async def app_lifespan(_server: FastMCP) -> AsyncIterator[DeviceManager]:
    """Create shared aiohttp session and device manager for the server lifetime."""
    configs = load_config()
    logger.info("Starting air-Q Cloud MCP server with %d device(s)", len(configs))
    timeout = aiohttp.ClientTimeout(total=30, connect=15)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        yield DeviceManager(session, configs)


mcp = FastMCP(
    name="air-Q Cloud",
    instructions=(
        "This server provides access to air-Q air quality data via the air-Q Cloud API. "
        "Use list_devices to see available devices. Most tools accept an "
        "optional 'device' parameter to select which device to query — "
        "if only one device is configured, it is selected automatically. "
        "For historical plots, prefer PNG unless the user explicitly requests "
        "another output format."
    ),
    lifespan=app_lifespan,
)

# Import tools and prompts to register them with the mcp instance.
from mcp_airq_cloud import prompts  # noqa: E402, F401
from mcp_airq_cloud.tools import read  # noqa: E402, F401

_HELP_TEXT = """\
This command supports two modes:

1. MCP server mode for Claude Desktop, Claude Code, OpenAI Codex, and other clients.
2. Direct CLI mode, where each MCP tool is exposed as a terminal subcommand.

CLI examples:

  mcp-airq-cloud list-devices
  mcp-airq-cloud get-air-quality --device "Living Room"
  mcp-airq-cloud get-air-quality-history --device "Living Room" --last-hours 24 --sensors co2 pm2_5
  mcp-airq-cloud plot-air-quality-history --sensor co2 --device "Living Room" --output co2.png

When started without subcommands, it runs as an MCP server over standard
input/output (stdio transport).

Set the AIRQ_CLOUD_DEVICES environment variable to a JSON array of device objects:

  [{"id": "<32-char-device-id>", "api_key": "<your-api-key>", "name": "Living Room"}]

Or set AIRQ_CLOUD_API_KEY as a global default and omit per-device api_key:

  AIRQ_CLOUD_API_KEY=<key> AIRQ_CLOUD_DEVICES='[{"id": "<id>", "name": "Living Room"}]'

To add this server to Claude Desktop, edit claude_desktop_config.json:

  {
    "mcpServers": {
      "air-Q Cloud": {
        "command": "mcp-airq-cloud",
        "env": {
          "AIRQ_CLOUD_DEVICES": "<json-array — see above>"
        }
      }
    }
  }

To add it to Claude Code, run:

  claude mcp add air-Q-Cloud mcp-airq-cloud -e AIRQ_CLOUD_DEVICES='[{"id":"<ID>","api_key":"<KEY>","name":"<Name>"}]'

Alternatively, set AIRQ_CLOUD_CONFIG_FILE to point to a JSON configuration file
with the same structure as the AIRQ_CLOUD_DEVICES array.

For more information, see: https://github.com/CorantGmbH/mcp-airq-cloud
"""


def run_cli(argv: list[str] | None = None) -> int:
    """Run the direct CLI mode."""
    from mcp_airq_cloud.cli import main as cli_main

    return cli_main(argv)


def main():
    """Entry point for the mcp-airq-cloud command."""
    argv = sys.argv[1:]

    if argv and argv[0] == "--version":
        print(f"mcp-airq-cloud {__version__}")
        return

    if argv and argv[0] in {"--help", "-h"}:
        print(f"mcp-airq-cloud {__version__} — MCP server for air-Q Cloud API\n")
        print(_HELP_TEXT, end="")
        return

    if argv and argv[0] in {"serve", "mcp"}:
        mcp.run(transport="stdio")
        return

    if argv:
        run_cli(argv)
        return

    if sys.stdin.isatty():
        print(f"mcp-airq-cloud {__version__} — MCP server for air-Q Cloud API\n")
        print(_HELP_TEXT, end="")
        return

    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
