# Changelog

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
