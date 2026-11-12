# Agent Guideline

Library to interact with physical environmental sensors and forecast data from web (when connectivity is available)
and provide an interface over a Mesh network (either MeshCore or Meshtastic).

This application is a Python 3.12 application that runs as a system service.

Source is contained with `src/raspberry_pi_mesh_weather`

## Testing Guidelines

Tests are located within `tests/`.

All core functionality should have tests to verify functionality and protect against regression bugs.

Static data sources to emulate live responses are generally stored in `tests/fixtures/` grouped by the source.
The fixture name should be short and descriptive for the test contents, eg: "good_response.json" or "too_many_calls.json".

## Coding Guidelines

Python code is indented with tab characters.

## Changelog Guidelines

All changes, fixes, and major items should be added to the `CHANGELOG.md` under the `## [NEXT] - YYYY-MM-DD` group.
If this group does not exist, one should be created to store the features for the next version.
Note, `YYYY-MM-DD` is **literal** for unreleased versions; the date stamp is usually undetermined so a placeholder is used.