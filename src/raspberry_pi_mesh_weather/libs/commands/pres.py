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

from .handler import command, CommandResponse, CommandResponseError, CommandResponseSuccess
from raspberry_pi_mesh_weather.libs.pressure import get_pressure, get_pressure_change


@command('pres', direct=True, group=True)
@command('pressure', direct=True, group=True)
def cmd_pressure(target: str | None = None) -> CommandResponse:
	pressure = get_pressure()
	pressure_change = get_pressure_change()

	if pressure is None:
		return CommandResponseError('Sorry, but no pressure is available right now.')

	pressure = round(pressure, 2)

	if pressure_change is None:
		# No local pressure data, so no trend to report.
		return CommandResponseSuccess(f"Pressure is {pressure}hPa")

	if pressure_change == 1:
		return CommandResponseSuccess(f"Pressure has rose to {pressure}hPa!  Expect sunny weather.")

	if pressure_change == -1:
		return CommandResponseSuccess(f"Pressure has fallen to {pressure}hPa!  Expect rainy weather.")

	return CommandResponseSuccess(f"Pressure is a stable {pressure}hPa")
