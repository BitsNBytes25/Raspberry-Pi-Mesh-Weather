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
from .handler import command, CommandResponse, CommandResponseNoData, CommandResponseSuccess
from raspberry_pi_mesh_weather.libs.wind import get_wind_compass, get_wind_gust, get_wind_speed


@command('wind', direct=True, group=True)
def cmd_wind(target: str | None = None) -> CommandResponse:
	"""
	Report the current wind from the OpenWeatherMap service.

	No local wind sensor is attached, so this is always service-derived.
	"""
	wind_speed = get_wind_speed()
	if wind_speed is None:
		return CommandResponseNoData('Sorry, but no wind available')

	message = f'Current wind here is {round(wind_speed, 1)} m/s'
	compass = get_wind_compass()
	if compass:
		message += f' {compass}'
	gust = get_wind_gust()
	if gust is not None:
		message += f' (gust {round(gust, 1)} m/s)'
	return CommandResponseSuccess(message)
