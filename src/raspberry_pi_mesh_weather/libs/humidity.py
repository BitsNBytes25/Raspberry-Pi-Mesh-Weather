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

from raspberry_pi_mesh_weather.libs.system_state import state
from raspberry_pi_mesh_weather.libs import open_weather_map


def get_humidity():
	"""
	Get the current humidity, falling back to OpenWeatherMap current
	conditions when the local sensor is unavailable.
	"""
	humidity = state.get('humidity')
	if humidity is not None:
		return humidity
	conditions = open_weather_map.get_current_conditions()
	return conditions['humidity'] if conditions else None


def set_humidity(humidity):
	state.set_with_history('humidity', humidity)
