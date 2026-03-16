"""Guide strings for air-Q sensor interpretation.

Imported by both prompts.py (to expose as MCP prompts) and read.py
(to embed directly in tool responses so the context is always present,
regardless of whether the client invokes the prompt explicitly).
"""

# ---------------------------------------------------------------------------
# Structured sensor data — single source of truth for the sensor guide
# ---------------------------------------------------------------------------

# Each row: (matching_keys, display_key, unit_or_range, description)
_Row = tuple[frozenset[str], str, str, str]


def _e(keys: str | set[str], display: str, unit: str, desc: str) -> _Row:
    """Create a sensor row. *keys* may be a single key or a set."""
    if isinstance(keys, str):
        keys = {keys}
    return (frozenset(keys), display, unit, desc)


# (section_title, column_headers, rows)
_Category = tuple[str, tuple[str, str, str], list[_Row]]

_SENSOR_CATEGORIES: list[_Category] = [
    (
        "Quality indices — higher is always better",
        ("Key", "Range", "Meaning"),
        [
            _e(
                "health",
                "health",
                "0–1000",
                "Overall air quality health score. -200 = gas alarm, -800 = fire alarm.",
            ),
            _e(
                "performance",
                "performance",
                "0–1000",
                "Estimated cognitive performance index.",
            ),
            _e(
                "mold",
                "mold",
                "0–100 %",
                "Mold-FREE index. 100 % = no mold risk; 0 % = ventilation insufficient.",
            ),
            _e(
                "virus",
                "virus",
                "0–100 %",
                "Low-virus-transmission index. 100 % = fine; 0 % = ventilation insufficient."
                " Uses CO₂ as aerosol proxy.",
            ),
        ],
    ),
    (
        "Climate",
        ("Key", "Unit", "Notes"),
        [
            _e("temperature", "temperature", "°C", "Configurable: degF, K"),
            _e("humidity", "humidity", "%", "Relative humidity"),
            _e("humidity_abs", "humidity_abs", "g/m³", "Absolute humidity"),
            _e("dewpt", "dewpt", "°C", "Dew point. Configurable: degF, K"),
            _e(
                "pressure",
                "pressure",
                "hPa",
                "Absolute air pressure. Configurable: kPa, mbar, bar, psi",
            ),
            _e(
                "pressure_rel",
                "pressure_rel",
                "hPa",
                "Relative pressure (QNH), only if altitude configured",
            ),
        ],
    ),
    (
        "Gases",
        ("Key", "Unit", "Notes"),
        [
            _e("co2", "co2", "ppm", "CO₂. Auto-calibrated baseline at 410 ppm."),
            _e("tvoc", "tvoc", "ppb", "Total VOC (electrochemical)."),
            _e(
                "tvoc_ionsc",
                "tvoc_ionsc",
                "ppb",
                "Total VOC (PID sensor, ION Science).",
            ),
            _e(
                "co",
                "co",
                "mg/m³",
                "Carbon monoxide. Fire alarm threshold: > 200 mg/m³.",
            ),
            _e(
                "no2",
                "no2",
                "µg/m³",
                "Nitrogen dioxide. Gas alarm threshold: > 20 000 µg/m³.",
            ),
            _e("so2", "so2", "µg/m³", "Sulfur dioxide."),
            _e("o3", "o3", "µg/m³", "Ozone. Gas alarm threshold: > 1 000 µg/m³."),
            _e(
                "h2s",
                "h2s",
                "µg/m³",
                "Hydrogen sulfide. Gas alarm threshold: > 50 000 µg/m³.",
            ),
            _e(
                "oxygen",
                "oxygen",
                "%",
                "O₂. Normal: ~20.9 %. Gas alarm threshold: < 13 %.",
            ),
            _e("ethanol", "ethanol", "µg/m³", ""),
            _e("n2o", "n2o", "µg/m³", "Nitrous oxide."),
            _e(
                "nh3_mr100",
                "nh3_mr100",
                "µg/m³",
                "Ammonia. Gas alarm threshold: > 100 000 µg/m³.",
            ),
            _e("acid_m100", "acid_m100", "ppb", "Organic acids."),
            _e("h2_m1000", "h2_m1000", "µg/m³", "Hydrogen."),
            _e("no_m250", "no_m250", "µg/m³", "Nitric oxide."),
            _e(
                "cl2_m20",
                "cl2_m20",
                "µg/m³",
                "Chlorine. Gas alarm threshold: > 50 000 µg/m³.",
            ),
            _e(
                "ch2o_m10",
                "ch2o_m10",
                "µg/m³",
                "Formaldehyde. Gas alarm threshold: > 2 000 µg/m³.",
            ),
            _e(
                "c3h8_mipex",
                "c3h8_mipex",
                "%",
                "Propane. Gas alarm threshold: > 0.25 %.",
            ),
            _e("ch4_mipex", "ch4_mipex", "%", "Methane. Gas alarm threshold: > 0.5 %."),
            _e("r32", "r32", "%", "Refrigerant R-32."),
            _e("r454b", "r454b", "%", "Refrigerant R-454B."),
            _e("r454c", "r454c", "%", "Refrigerant R-454C."),
        ],
    ),
    (
        "Particulate matter",
        ("Key", "Unit", "Notes"),
        [
            _e("pm1", "pm1", "µg/m³", "PM1.0 mass concentration."),
            _e(
                "pm2_5",
                "pm2_5",
                "µg/m³",
                "PM2.5 mass concentration. By definition: pm1 ≤ pm2_5 ≤ pm10.",
            ),
            _e(
                "pm10",
                "pm10",
                "µg/m³",
                "PM10 mass concentration. Fire alarm threshold: PM1 > 400 µg/m³.",
            ),
            _e("typps", "typps", "µm", "Typical (mean) particle size."),
            _e(
                {"cnt0_3", "cnt0_5", "cnt1", "cnt2_5", "cnt5", "cnt10"},
                "cnt0_3 … cnt10",
                "#/100 ml",
                "Particle count for sizes > 0.3, 0.5, 1, 2.5, 5, 10 µm.",
            ),
            _e(
                {"pm1_sps30", "pm2_5_sps30", "pm10_sps30"},
                "pm1_sps30 … pm10_sps30",
                "µg/m³",
                "PM fractions from optional Sensirion SPS30.",
            ),
            _e(
                {
                    "cnt0_5_sps30",
                    "cnt1_sps30",
                    "cnt2_5_sps30",
                    "cnt4_sps30",
                    "cnt10_sps30",
                },
                "cnt0_5_sps30 … cnt10_sps30",
                "1/cm³",
                "Particle counts from optional Sensirion SPS30.",
            ),
        ],
    ),
    (
        "Acoustics",
        ("Key", "Unit", "Notes"),
        [
            _e(
                "sound",
                "sound",
                "dB(A)",
                "Average noise level over the measurement period.",
            ),
            _e(
                "sound_max",
                "sound_max",
                "dB(A)",
                "Peak noise level within the measurement period.",
            ),
        ],
    ),
    (
        "Radon",
        ("Key", "Unit", "Notes"),
        [
            _e(
                "radon",
                "radon",
                "Bq/m³",
                "Radon activity. Configurable: pCi/L. WHO reference level: 100 Bq/m³.",
            ),
        ],
    ),
    (
        "Metadata fields (not sensor measurements)",
        ("Key", "Unit", "Notes"),
        [
            _e("timestamp", "timestamp", "ms", "Unix epoch in milliseconds."),
            _e("uptime", "uptime", "s", "Device runtime since last reboot."),
            _e("measuretime", "measuretime", "ms", "Duration of the measurement cycle."),
            _e(
                "dco2dt",
                "dco2dt",
                "ppb/s",
                "CO₂ rate of change. Only available after 200 s of runtime.",
            ),
            _e(
                "dhdt",
                "dhdt",
                "mg/m³/s",
                "Absolute humidity rate of change. Used internally for sensor compensation.",
            ),
            _e(
                "deviceid",
                "deviceid",
                "—",
                "Device serial (first 10 chars) + unique suffix.",
            ),
            _e(
                "status",
                "status",
                "—",
                '"OK" or JSON object with per-sensor status messages.',
            ),
        ],
    ),
]

_FULL_GUIDE_FOOTER = """\

## Alarm thresholds (for reference)

Fire alarm (if enabled): CO > 200 mg/m³, PM1 > 400 µg/m³, or temperature > 70 °C.
Gas alarm (if enabled): O₂ < 13 %, NO₂ > 20 000 µg/m³, O₃ > 1 000 µg/m³,
  H₂S > 50 000 µg/m³, CH₂O > 2 000 µg/m³, Cl₂ > 50 000 µg/m³,
  NH₃ > 100 000 µg/m³, CH₄ > 0.5 %, C₃H₈ > 0.25 %.

## Unit configuration

Default units apply unless the device is configured otherwise via the `units` config key.
The actual unit in use can be verified by reading the SensorInfo from GET /config.
"""


# ---------------------------------------------------------------------------
# Guide builder
# ---------------------------------------------------------------------------


def _format_table(columns: tuple[str, str, str], rows: list[_Row]) -> str:
    """Render *rows* as a markdown table with the given column headers."""
    lines = [
        f"| {columns[0]} | {columns[1]} | {columns[2]} |",
        "|---|---|---|",
    ]
    for _, display, unit, desc in rows:
        lines.append(f"| {display} | {unit} | {desc} |")
    return "\n".join(lines)


def build_sensor_guide(data_keys: frozenset[str] | set[str]) -> str:
    """Build a sensor guide filtered to sensors present in *data_keys*.

    Only categories that contain at least one matching sensor are included.
    Returns an empty string when nothing matches.
    """
    sections: list[str] = []
    for title, columns, rows in _SENSOR_CATEGORIES:
        matching = [r for r in rows if r[0] & data_keys]
        if matching:
            sections.append(f"## {title}\n\n{_format_table(columns, matching)}")
    if not sections:
        return ""
    return "# air-Q Sensor Interpretation Guide\n\n" + "\n\n".join(sections)


def sensor_unit(data_key: str) -> str | None:
    """Return the default unit for one sensor key, if known."""
    key = data_key.lower()
    for _, _, rows in _SENSOR_CATEGORIES:
        for keys, _, unit, _ in rows:
            if key in keys:
                return unit
    return None


# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

# All known sensor keys — used to generate the full (unfiltered) guide.
_ALL_KEYS: frozenset[str] = frozenset().union(*(keys for _, _, rows in _SENSOR_CATEGORIES for keys, _, _, _ in rows))

SENSOR_GUIDE = build_sensor_guide(_ALL_KEYS) + _FULL_GUIDE_FOOTER
