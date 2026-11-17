# Raspberry Pi Mesh Weather
#
# https://github.com/BitsNBytes25/Raspberry-Pi-Mesh-Weather
#
# Copyright (c) 2026 Charlie Powell
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://gnu.org>.

import logging

from .handler import command, CommandResponse, CommandResponseError, CommandResponseSuccess
from raspberry_pi_mesh_weather.libs.config import config
from raspberry_pi_mesh_weather.libs.open_weather_map import OpenWeatherMap

# Descriptions with no precipitation / disruptive weather.  Used to decide
# when to lead with the incoming weather (the "around" phrasing) instead of
# the calm current state.
CALM_WEATHER = {
	'clear sky', 'few clouds', 'scattered clouds',
	'partly cloudy', 'broken clouds', 'overcast clouds',
}


def _time_label(hour: int) -> str:
	"""
	Format a 24-hour time to a short human readable format.

	'0' => 12 AM
	'11' => 11 AM
	'20' => 8 PM

	:param hour: 24-hour time
	"""
	period = "A" if hour < 12 else "P"
	hour12 = hour % 12 or 12
	return f"{hour12}{period}"


def _cap_first(text: str) -> str:
	"""
	Uppercase only the first letter of `text`, leaving the rest unchanged.

	Avoids str.capitalize(), which would lowercase an "AM/PM" in the middle.
	"""
	return text[:1].upper() + text[1:]


def _temp_label(entry: dict) -> str:
	"""
	Compact Celsius / Fahrenheit label for a single entry.

	:param entry: a forecast entry dict with a 'temp' key
	"""
	f = int(round(entry['temp'] * 1.8 + 32))
	return f"{entry['temp']:.0f}°C/{f}°F"


def _forecast_summary(entries: list[dict]) -> str:
	"""
	Build a compact single-state narrative from the chronological entries.

	Only one weather state is described — the first noteworthy one. Calm
	cloud-cover states are skipped in favor of any active weather:
	  - 'Light rain'                  (single state for the whole window)
	  - 'Light rain until 3A'         (active now, ends when it changes)
	  - 'Light rain around 7A'        (calm now, active arriving at N)
	"""
	# Run-length group the entries by description (they are chronological).
	runs = []
	for entry in entries:
		if runs and runs[-1][0] == entry['description']:
			continue
		runs.append((entry['description'], entry))

	a_desc = runs[0][0]

	# Single state covers the whole window.
	if len(runs) == 1:
		return _cap_first(a_desc)

	if a_desc in CALM_WEATHER:
		# Calm skies now; lead with the first noteworthy weather event.
		for b_desc, b_entry in runs[1:]:
			if b_desc not in CALM_WEATHER:
				return _cap_first(b_desc) + f" around {_time_label(b_entry['hour'])}"
		# No noteworthy weather; everything is calm.
		return _cap_first(a_desc)

	# Notable weather now; it lasts until the next change.
	return _cap_first(a_desc) + f" until {_time_label(runs[1][1]['hour'])}"


@command('forecast', direct=True, group=True)
def cmd_daily_forecast(target: str | None = None) -> CommandResponse:
	"""
	Fetches the next forecast entries and broadcasts a compact two-state
	summary over the mesh network.
	"""
	api = config.weather.openweather_api_key
	lat = config.location.lat
	lon = config.location.lon
	label = config.location.label

	if api == '':
		logging.error('No API key set for openweathermap.org, no forecast data available')
		return CommandResponseError('No API set for OpenWeatherMap.org, unable to fetch forecast data.')

	if lat is None:
		logging.error('No latitude set, unable to pull forecast data.')
		return CommandResponseError('No latitude set, unable to pull forecast data.')

	if lon is None:
		logging.error('No longitude set, unable to pull forecast data.')
		return CommandResponseError('No longitude set, unable to pull forecast data.')

	header = f'Forecast for {label}' if label else 'Forecast'

	logging.debug('--- Running Daily Weather Forecast Fetch ---')
	try:
		# Initialize the OpenWeatherMap client (it will read OPENWEATHERMAP_API_KEY)
		weather_client = OpenWeatherMap()
		entries = weather_client.get_daily_forecast(4)

		if not entries:
			print('Weather Forecast: Failed to retrieve data.')
			return CommandResponseError('Failed to retrieve forecast data.')

		summary = _forecast_summary(entries)
		lines = []
		for entry in entries:
			time = _time_label(entry['hour'])
			spacer = (4 - len(time)) * ' '
			lines.append(f"{entry['icon']}  {time}:{spacer}{_temp_label(entry)}")

		message = f"{header}: {summary}\n" + "\n".join(lines)
		return CommandResponseSuccess(message)
	except Exception as e:
		error_msg = f"Daily Weather: An error occurred during forecast fetching/broadcasting: {e}"
		print(f"Weather Forecast Error: {e}")
		return CommandResponseError(error_msg)
