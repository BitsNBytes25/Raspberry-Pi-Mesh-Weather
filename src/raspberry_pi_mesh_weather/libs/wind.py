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
#
from raspberry_pi_mesh_weather.libs import open_weather_map

# 16-point compass names, in the order the bearing sweeps round the dial.
_COMPASS_SECTORS = [
	'N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE',
	'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW',
]


def _compass_from_degree(deg: float) -> str:
	"""
	Map a 0-360 wind bearing to its 16-point compass shorthand.

	:param deg: bearing in degrees (the direction the wind is blowing from).
	:return: one of the 16-point compass names (e.g. "NNW").
	"""
	deg = deg % 360.0
	return _COMPASS_SECTORS[int((deg + 11.25) / 22.5) % 16]


def get_wind_speed() -> float | None:
	"""
	Get the current wind speed in m/s from OpenWeatherMap.

	There is no local wind sensor, so this is always service-derived.

	:return: wind speed in m/s, or None if unavailable.
	"""
	conditions = open_weather_map.get_current_conditions()
	return conditions.get('wind_speed') if conditions else None


def get_wind_gust() -> float | None:
	"""
	Get the current gust speed in m/s from OpenWeatherMap.

	:return: gust speed in m/s, or None if unavailable.
	"""
	conditions = open_weather_map.get_current_conditions()
	return conditions.get('wind_gust') if conditions else None


def get_wind_compass() -> str | None:
	"""
	Get the current wind direction as a 16-point compass shorthand.

	:return: e.g. "NNW" (the direction the wind is blowing from), or None if
			unavailable.
	"""
	conditions = open_weather_map.get_current_conditions()
	if conditions is None:
		return None
	deg = conditions.get('wind_deg')
	if deg is None:
		return None
	return _compass_from_degree(deg)
