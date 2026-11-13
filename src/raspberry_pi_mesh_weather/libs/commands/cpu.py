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

import os
import logging

from .handler import command, CommandResponse, CommandResponseSuccess


@command('cpu', direct=True)
def cmd_cpu(target: str | None = None) -> CommandResponse:
	temp = None
	try:
		# Default location of CPU thermal probe for Raspberry Pis
		with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
			temp = float(f.read()) / 1000
	except FileNotFoundError:
		logging.error('Could not read CPU temperature')

	load = os.getloadavg()
	load = round(load[1])
	if temp is not None:
		return CommandResponseSuccess(f"CPU: {load}% load and {temp}°C")
	else:
		return CommandResponseSuccess(f"CPU: {load}% load")
