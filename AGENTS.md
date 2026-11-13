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

Do not over-complicate solutions, prefer a simple solution over complex ones.

DRY - Don't Repeat Yourself; once a given set of functionality is used by 2 or more modules, 
it should probably be in a shared location.

## Changelog Guidelines

All changes, fixes, and major items should be added to the `CHANGELOG.md` under the `## [NEXT] - YYYY-MM-DD` group.
If this group does not exist, one should be created to store the features for the next version.
Note, `YYYY-MM-DD` is **literal** for unreleased versions; the date stamp is usually undetermined so a placeholder is used.

**DO NOT RENAME "YYYY-MM-DD" TO TODAY'S DATE!!!!!!!!!**

Let me repeat that, **KEEP LITERALLY `## [NEXT] - YYYY-MM-DD` AS THE CHANGELOG HEADER**!

## Command Guidelines

A major feature of this project is listening for messages over a mesh network and provide responses
via channels (like `#weather`) or direct messages.
Meshtastic supports 200 characters and MeshCore supports 130 characters, so all command responses
must be under 130 characters in length.
Exceeding this 130 character limit will not result in exceptions or errors, but will result in
data truncation when sending the reply via the radio.
