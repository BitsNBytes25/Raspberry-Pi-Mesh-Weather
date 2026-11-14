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

from .handler import command, CommandResponse, CommandResponseNoData, CommandResponseSuccess
from raspberry_pi_mesh_weather.libs.config import config
from raspberry_pi_mesh_weather.libs.humidity import get_humidity
from raspberry_pi_mesh_weather.libs.icon_map import get_icon
from raspberry_pi_mesh_weather.libs.pressure import get_pressure, get_pressure_change
from raspberry_pi_mesh_weather.libs.temperature import get_temperature
from raspberry_pi_mesh_weather.libs.wind import get_wind_compass, get_wind_speed


def _weather_icon(temp: float | None, humidity: float | None, pressure_change: float | None) -> str:
	"""
	Pick a weather icon to represent the current local conditions.

	:param temp: Current temperature in °C (or None if unavailable)
	:param humidity: Current relative humidity in % (or None if unavailable)
	:param pressure_change: 1 if pressure is rising, -1 if falling, 0 if stable.
	:return: Icon glyph for the current conditions, resolved via the active
	         icon style (see libs/icon_map.py).
	"""
	if temp is not None and temp < 1:
		# Freezing - takes precedence over everything else.
		return get_icon('freezing')
	if pressure_change == -1:
		# Pressure falling - rain is likely.
		return get_icon('rain')
	if pressure_change == 1:
		# Pressure rising - expect sunshine.
		return get_icon('sun')
	if humidity is not None and humidity > 70:
		# Muggy and damp - expect overcast.
		return get_icon('sun_clouds')
	return get_icon('sun')


@command('all', group=True, direct=True)
def cmd_all_sensors(target: str | None = None) -> CommandResponse:
	"""
	Report all available local sensor readings along with the current weather.
	"""
	temp = get_temperature()
	humidity = get_humidity()
	pressure = get_pressure()
	pressure_change = get_pressure_change()
	wind_speed = get_wind_speed()
	wind_compass = get_wind_compass()
	sensors = []

	if temp is not None:
		fake_temp = round(temp * 9/5 + 32)
		sensors.append(f"{temp:.1f}°C ({fake_temp}°F)")
	if humidity is not None:
		sensors.append(f"{humidity:.1f}% humidity")
	if pressure is not None:
		if pressure_change is not None:
			if pressure_change == 1:
				trend = 'rising'
			elif pressure_change == -1:
				trend = 'falling'
			else:
				trend = 'stable'
			sensors.append(f"{pressure:.1f} hPa ({trend})")
		else:
			sensors.append(f"{pressure:.1f} hPa")
	if wind_speed is not None:
		compass = f' {wind_compass}' if wind_compass else ''
		sensors.append(f"wind {wind_speed:.0f} m/s{compass}")

	if len(sensors) > 0:
		icon = _weather_icon(temp, humidity, pressure_change)
		if config.location.label:
			header = f'Weather in {config.location.label}:'
		else:
			header = 'Current weather here:'
		return CommandResponseSuccess(f'{icon} {header}\n' + ' | '.join(sensors))
	else:
		return CommandResponseNoData('Sorry, but no sensor data is available')
