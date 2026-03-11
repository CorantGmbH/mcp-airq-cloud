# Changelog

## [0.1.4] - 2026-03-11

### Fixed

- Resolve pylint `too-many-return-statements` in `errors.py` (disable inline)
- Resolve pylint `too-many-locals` in `get_air_quality_history` by extracting `_parse_time_range` helper

## [0.1.3] - 2026-03-11

### Added

- Default config file path: `~/.config/airq-cloud-devices.json` is loaded automatically if no environment variable is set

## [0.1.2] - 2026-03-11

### Fixed

- Add `mcp-name` comment to README for MCP Registry ownership validation

## [0.1.1] - 2026-03-11

### Changed

- Add badges (MCP, PyPI, downloads, Python, license, tests, coverage) to README
- Mention my.air-q.com as source for API key and device ID
- Improve test coverage to 99%

## [0.1.0] - 2026-03-11

### Added

- Initial release with 3 read-only tools via the air-Q Cloud API
- `list_devices` — list configured cloud devices
- `get_air_quality` — get latest sensor data (supports device/location/group selection)
- `get_air_quality_history` — get historical data within a time range
- Multi-device support with name, location, and group resolution
- Sensor interpretation guide embedded in tool responses
- Per-device or global API key configuration
