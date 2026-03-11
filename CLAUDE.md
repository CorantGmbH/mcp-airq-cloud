# CLAUDE.md

## Project Overview

MCP (Model Context Protocol) server for the [air-Q](https://www.air-q.com) Cloud API. Enables Claude Desktop, Claude Code, and other MCP clients to query air-Q sensor data remotely via the cloud REST API.

Unlike [mcp-airq](../mcp-airq/) (local network, aioairq), this server communicates with `https://air-q-cloud.de/open_api/v3/` using API keys.

## Architecture

```
Claude Desktop/Code/Web
    └── MCP Client (JSON-RPC 2.0 over STDIO)
            └── mcp-airq-cloud (this project)
                    └── aiohttp → air-Q Cloud API (HTTPS + API key)
```

### Key Modules

| Module | Purpose |
|--------|---------|
| `server.py` | FastMCP instance, lifespan (aiohttp session), entry point |
| `config.py` | Loads device config from `AIRQ_CLOUD_DEVICES` env var or `AIRQ_CLOUD_CONFIG_FILE` |
| `cloud_device.py` | `CloudDevice`: thin wrapper around the 2 Cloud API endpoints |
| `devices.py` | `DeviceManager`: caches `CloudDevice` instances, resolves device names |
| `errors.py` | `@handle_cloud_errors` decorator — catches HTTP/network exceptions |
| `guides.py` | Structured sensor interpretation guide |
| `prompts.py` | MCP prompt for sensor guide |
| `tools/read.py` | 3 read-only tools (list_devices, get_air_quality, get_air_quality_history) |

### Design Patterns

- **Lifespan**: `aiohttp.ClientSession` is created/closed in `app_lifespan()`. The `DeviceManager` is yielded as the lifespan context.
- **Error handling**: The `@handle_cloud_errors` decorator wraps all tool functions. It catches HTTP status errors (401, 403, 404), network errors, and timeouts.
- **ToolAnnotations**: All tools are annotated with `readOnlyHint=True`.
- **Multi-device**: Each tool has an optional `device: str | None` parameter. Single-device setups auto-resolve; multi-device uses case-insensitive substring matching.

## Commands

```bash
# Install (editable, with dev deps)
pip install -e ".[dev]"

# Run tests
pytest

# Run the server (STDIO transport)
mcp-airq-cloud

# Build for distribution
pip install hatch
hatch build
```

## Device Configuration

Via environment variable `AIRQ_CLOUD_DEVICES` (JSON array):

```json
[
  {"id": "de45d2ed777780c96c0deae7a220b745", "api_key": "your-key", "name": "Living Room"}
]
```

Or via `AIRQ_CLOUD_CONFIG_FILE` pointing to a JSON file with the same structure.

Global fallback API key: `AIRQ_CLOUD_API_KEY` (used when per-device `api_key` is omitted).

## Dependencies

- `mcp` — MCP SDK (FastMCP)
- `aiohttp` — async HTTP client for Cloud API requests

## Code Conventions

- Python ≥ 3.11, type hints with built-in generics (`list`, `dict`, `str | None`)
- All tools are async, return `str` (JSON-serialized or plain text)
- Tools use docstrings as their MCP description (FastMCP extracts them automatically)
- Tests use `pytest` + `pytest-asyncio`, mock HTTP methods — no real API key needed
- Keep the tool layer thin

## Versioning

When bumping the version, update it in **all three** of these files:

1. `pyproject.toml` — `version = "x.y.z"`
2. `server.json` — `"version": "x.y.z"` (appears twice: top-level and inside `packages[]`)
3. `CHANGELOG.md` — add a new `## [x.y.z] - YYYY-MM-DD` section

## Related Projects

- **mcp-airq**: `../mcp-airq/` — MCP server for direct local network access to air-Q devices
- **aioairq**: `../../aioairq/` — the async Python library for local air-Q communication
