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


def get_pressure() -> float:
	return state.get('pressure')


def get_pressure_change() -> float:
	"""
	Get if the pressure is quickly rising or falling.
	If rising (>1.5hPa per hour), return 1.
	If falling (>1.5hPa per hour), return -1.
	else, return 0.

	:return:
	"""
	first_entry = state.get_earliest('pressure')
	last_entry = state.get('pressure')

	if first_entry is None or last_entry is None:
		# Data not available yet
		return 0
	diff = abs(last_entry - first_entry)
	if diff >= 1.5:
		return 1 if last_entry > first_entry else -1
	else:
		return 0


def set_pressure(pressure: float):
	# Store the current sensor measurement
	state.set_with_history('pressure', pressure)
