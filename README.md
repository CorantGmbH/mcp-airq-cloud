# mcp-airq-cloud

MCP server for the [air-Q](https://www.air-q.com) Cloud API — access air quality data from anywhere.

Unlike [mcp-airq](https://github.com/CorantGmbH/mcp-airq) (which communicates directly with devices on the local network), this server uses the **air-Q Cloud REST API** to retrieve sensor data remotely.

## Tools

| Tool | Description |
|------|-------------|
| `list_devices` | List configured air-Q Cloud devices |
| `get_air_quality` | Get latest sensor readings (supports device/location/group selection) |
| `get_air_quality_history` | Get historical data within a time range |

All tools are **read-only** — the Cloud API does not support device configuration or control.

## Installation

```bash
pip install mcp-airq-cloud
```

Or install from source:

```bash
git clone https://github.com/CorantGmbH/mcp-airq-cloud.git
cd mcp-airq-cloud
pip install -e ".[dev]"
```

## Configuration

You need a **Cloud API key** and the **32-character device ID** for each device. Both can be obtained at [my.air-q.com](https://my.air-q.com).

### Option 1: Environment variable (inline JSON)

```bash
export AIRQ_CLOUD_DEVICES='[{"id": "de45d2ed777780c96c0deae7a220b745", "api_key": "your-api-key", "name": "Living Room"}]'
```

### Option 2: Config file

```bash
export AIRQ_CLOUD_CONFIG_FILE=/path/to/devices.json
```

### Option 3: Global API key

If all devices share the same API key, set it once:

```bash
export AIRQ_CLOUD_API_KEY="your-api-key"
export AIRQ_CLOUD_DEVICES='[{"id": "de45d2ed777780c96c0deae7a220b745", "name": "Living Room"}]'
```

### Device config fields

| Field | Required | Description |
|-------|----------|-------------|
| `id` | yes | 32-character cloud device ID |
| `api_key` | no | Per-device API key (falls back to `AIRQ_CLOUD_API_KEY`) |
| `name` | no | Friendly name (defaults to first 8 chars of ID) |
| `location` | no | Location for grouping (e.g. "Wohnzimmer") |
| `group` | no | Group for grouping (e.g. "zu Hause") |

## Usage with Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "air-Q Cloud": {
      "command": "mcp-airq-cloud",
      "env": {
        "AIRQ_CLOUD_DEVICES": "[{\"id\": \"<device-id>\", \"api_key\": \"<key>\", \"name\": \"Living Room\"}]"
      }
    }
  }
}
```

## Usage with Claude Code

```bash
claude mcp add air-Q-Cloud mcp-airq-cloud \
  -e AIRQ_CLOUD_DEVICES='[{"id":"<ID>","api_key":"<KEY>","name":"<Name>"}]'
```

## Development

```bash
pip install -e ".[dev]"
pytest
```

## License

Apache 2.0 — see [LICENSE](LICENSE).
