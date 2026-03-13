# Changelog

## [1.1.1] - 2026-03-13

### Changed

- Development workflow now uses a project-local `.venv` plus `uv.lock` for
  reproducible environments instead of machine-specific Python/PATH setups.
- Replaced `pylint` and `black` in local validation with `ruff check` and
  `ruff format`, and aligned pre-commit plus CI with the same `uv run`-based
  commands.
- `pyright` now resolves imports from the repo-local `.venv` instead of
  absolute user-specific paths.

## [1.1.0] - 2026-03-13

### Changed

- `get_air_quality_history` now returns column-oriented JSON (key `columns`
  instead of `data`), compact separators, and timestamps in Unix seconds
  (divided by 1000). Matches the format of mcp-airq 1.3.0.
- `get_air_quality_history` validates requested sensors and returns a clear
  error message if any are unavailable, listing available sensors.
- Sensor guide display names normalized to lowercase (e.g. `TypPS` → `typps`,
  `ch2o_M10` → `ch2o_m10`) to match Cloud API key casing.
- Sensor name docstring updated to lowercase throughout.

## [1.0.0] - 2026-03-11

### Added

- `get_air_quality_history`: new `sensors` parameter — filter response to specific sensor names only (e.g. `["pm1", "pm2_5", "pm10"]`), reducing response size by up to 98% for large time ranges
- `get_air_quality_history`: new `max_points` parameter — evenly downsample data to at most N points (useful for charting)
- Full sensor name reference added to `get_air_quality_history` docstring (all sensors from the air-Q technical documentation)

### Changed

- Improved tool docstrings: prominent data-volume warning in `get_air_quality_history`; corrected examples in `get_air_quality` (`device` vs. `location`)
- Development status classifier updated from Alpha to Production/Stable

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
