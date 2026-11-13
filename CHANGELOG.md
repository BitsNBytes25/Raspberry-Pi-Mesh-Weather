# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [NEXT] - YYYY-MM-DD

### Added

- **`humidity` command** — The full `humidity` command is now supported as a direct message command and as `!humidity` on the weather channel, alongside the existing `humid` shorthand. Both resolve to the same response. The `--test` daemon command list now includes `humidity` as well.
- **`temp` command tests** — Unit tests covering the no-temperature and no-humidity paths and every temperature band (freezing, cold, chilly, comfortable, warm, hot, oppressive), including the dry-air descriptions in the 18–24°C band.
- **Heat index tests** — Unit tests for `get_heat_index`, including the sub-26.7°C applicability threshold and known values.
- **`weather_forecast` tests** — Unit tests for `WeatherForecast`: init validation (missing API key / missing location), `get_daily_forecast` against the Columbus fixture (including the no-today-match fallback, request-failure, and malformed-response paths), and `get_description` period-window logic.

### Changed

- **`forecast` command** — Now shows a rolling forecast of the next entries in chronological order (starting from now) instead of a fixed "today" summary, so an evening call starts with the current evening and spills into tomorrow. `get_daily_forecast` returns a list of normalized entries (dt/hour/date/temp/feels_like/humidity/pop/description/icon); the narrative `get_description` and its period-window logic were removed. Entries are 3-hour buckets, so each is labelled by its actual clock time (e.g. "6:00 PM"), with a "Tomorrow" prefix for entries on the next day.
- **`forecast` command** — Output reformatted as a compact two-state summary to cut characters: a one-line narrative (e.g. "Light rain until 7 AM, then broken clouds") appears on the header line, followed by the current and change slots as `icon time: temp` (e.g. "🌧️ 10 PM: 7.0°C/45°F"). When skies are calm and precipitation is arriving, the narrative leads with the incoming weather ("Light rain around 7 AM"). The per-entry listing and the "Low/High" min/max line were removed.
- **`all` command** output reformatted to be cleaner
- **`temp` command** — Fixed a malformed oppressive-heat message (missing closing parenthesis) and a missing period at the end of the >29°C storm warning.
- **`temp` command** — Fixed the 18–24°C band falling through to a bare temperature readout when humidity is below 30%; added dry-air descriptions for that case instead.
- **`temp` command** — Switched from truncated (`int`) to rounded values for display and band selection so borderline temperatures (e.g. 24.9°C) get the correct description.
- **`temp` command** — Added a muggy (high-humidity) description to the 24–29°C band for temperatures where the heat index is not yet in the "limit activity" range.
- Cleanup output when running `daemon --test` to better view raw command responses
- **Commands refactored into `commands/` package** — The monolithic `libs/commands.py` was split into the `libs/commands/` package with one module per command (`help`, `ping`, `uptime`, `cpu`, `temp`, `pres`, `humidity`, `all_sensors`, `forecast`, `alerts`, `reboot`, `wake`, `net`) plus a separate `handler.py` holding the common functionality: the command registry, the `command()` decorator, the response classes, and the `get_command()` dispatch.
- **Command authorization now enforced** — The registry previously stored the raw command functions, so `get_command()` returned them unwrapped and the `auth` guard was bypassed, letting any radio run protected commands. The `handler` now stores the auth-wrapping function, so dispatch enforces the `auth` flag against the caller's public key; unauthorized callers (or a missing/empty key) get a "not authorized" response. `reboot`, `net`, and `wake` are now genuinely protected.
- **`ping` command** — No longer raises `TypeError` when invoked with no target (the channel/internal path calls commands with `None`); returns a bare `pong` instead of a crash.

## [1.0.0] - 2026-06-20

### Added

- **Environmental sensor tracking** — Pulls temperature, pressure, and humidity from locally-attached sensors and supports the **BME280**.
- **Mesh radio support** — Sends data, forecasts, and alerts over the mesh network and receives commands and queries:
  - **MeshCore**: listens on the `#weather` channel and responds with current weather data; direct messages also supported.
  - **Meshtastic**: listens on any configured channel for group messages.
  - Weather channel commands: `!temperature`, `!humidity`, `!pressure`, `!all`, `!forecast`, `!alerts`.
  - Direct message commands: `help`, `temperature`, `humidity`, `pressure`, `ping`, `uptime`, `cpu`, `wake`, `forecast`, `alerts`.
  - Administrative (authorized) commands: `reboot`, `net` (MeshCore only, via `auth_radios`).
- **Forecast and alerts** — Fetches a 1-day forecast and current weather alerts from OpenWeatherMap / NWS for mesh broadcast, with altitude-adjusted pressure readings (MSLP).
- **Home Assistant integration** — Uploads sensor metrics and discovered radios to a local Home Assistant installation, including optional custom device icons.
- **OLED display** — Displays basic diagnostic information on an attached display; send `wake` over the mesh to light the display for 2 minutes.
  - Supports the Microcenter OLED Display (345785).
- **MQTT packet capture** — Acts as a mesh observer by uploading raw packets to MQTT servers (multiple brokers supported, each with its own authentication, WebSocket, TLS, and MeshCore token auth options).
- **`config.yaml` configuration** — All features are optional and enabled/disabled via configuration, covering display, radio, sensors, location, weather, Home Assistant, security, and MQTT settings.
- **Modular installation** — Dependencies are installed per enabled hardware feature group (`radio-meshcore`, `radio-meshtastic`, `sensor-bme280`, `display-sh1106`) via `install.sh` / `uv sync`, so only what you use is installed.
- **Test suite** — Unit tests using pytest (with pytest-asyncio, pytest-mock, and pytest-cov).
- **`daemon` entry point** — A single systemd-managed daemon with `--debug` and `--test` modes.
- **License** — AGPLv3.

### Noted

- Currently only **serial/USB connected radios** are supported.
- Hardware features load lazily; the daemon starts on a machine without the full hardware stack attached (missing hardware is logged as an error).
- When enabling or disabling a feature, re-run `install.sh` (or `uv sync` with the matching group) so dependencies match the configuration.
