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
from datetime import date

from .handler import command, CommandResponse, CommandResponseError, CommandResponseSuccess
from raspberry_pi_mesh_weather.libs.config import config
from raspberry_pi_mesh_weather.libs.weather_forecast import WeatherForecast


def _time_label(hour: int) -> str:
	"""
	Format a 24-hour time to a human readable format.

	'0' => 12 AM
	'11' => 11 AM
	'20' => 8 PM

	:param hour: 24-hour time
	"""
	period = "AM" if hour < 12 else "PM"
	hour12 = hour % 12 or 12
	return f"{hour12} {period}"


@command('forecast', direct=True, group=True)
def cmd_daily_forecast(target: str | None = None) -> CommandResponse:
	"""
	Fetches the next forecast entries and broadcasts them over the mesh network.

	The next few entries are shown in chronological order, so an evening call
	starts with the current evening and spills into tomorrow, while a morning
	call shows the morning, afternoon and evening of the current day.
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

	if label == '':
		header = 'Forecast'
	else:
		header = f'Forecast for {label}'

	logging.debug('--- Running Daily Weather Forecast Fetch ---')
	try:
		# Initialize the weather client (it will read OPENWEATHERMAP_API_KEY)
		weather_client = WeatherForecast()
		entries = weather_client.get_daily_forecast(5)

		if not entries:
			print('Weather Forecast: Failed to retrieve data.')
			return CommandResponseError('Failed to retrieve forecast data.')

		low_temp = round(min(entry['temp'] for entry in entries))
		high_temp = round(max(entry['temp'] for entry in entries))
		low_f = int(round(low_temp * 1.8 + 32))
		high_f = int(round(high_temp * 1.8 + 32))

		# Show the next few entries, in chronological order.
		today = date.today().strftime('%Y-%m-%d')
		lines = []
		for entry in entries:
			label_text = _time_label(entry['hour'])
			entry_temp_f = int(round(entry['temp'] * 1.8 + 32))
			lines.append(f"{entry['icon']}  {label_text}: {entry['description']}, {entry['temp']:.1f}°C ({entry_temp_f}°F)")

		# Format the message for broadcasting
		message = (
			f"{header}:\n" + '\n'.join(lines) +
			f"\nLow/High: {low_temp}°C / {high_temp}°C ({low_f}°F / {high_f}°F)"
		)
		return CommandResponseSuccess(message)
	except Exception as e:
		error_msg = f"Daily Weather: An error occurred during forecast fetching/broadcasting: {e}"
		print(f"Weather Forecast Error: {e}")
		return CommandResponseError(error_msg)
