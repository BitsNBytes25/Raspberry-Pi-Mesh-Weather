# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
