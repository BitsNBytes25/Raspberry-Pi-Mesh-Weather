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


def get_pressure() -> float:
	"""
	Get the current pressure, falling back to OpenWeatherMap current
	conditions when the local sensor is unavailable.
	"""
	pressure = state.get('pressure')
	if pressure is not None:
		return pressure
	conditions = open_weather_map.get_current_conditions()
	return conditions['pressure'] if conditions else None


def get_pressure_change() -> float | None:
	"""
	Get if the pressure is quickly rising or falling.
	If rising (>1.5hPa per hour), return 1.0.
	If falling (>1.5hPa per hour), return -1.0.
	If stable, return 0.0.
	If no local pressure data is available, return None.

	:return:
	"""
	first_entry = state.get_earliest('pressure')
	last_entry = state.get('pressure')

	if first_entry is None or last_entry is None:
		# No local pressure data available.
		return None
	diff = abs(last_entry - first_entry)
	if diff >= 1.5:
		return 1.0 if last_entry > first_entry else -1.0
	else:
		return 0.0


def set_pressure(pressure: float):
	# Store the current sensor measurement
	state.set_with_history('pressure', pressure)
