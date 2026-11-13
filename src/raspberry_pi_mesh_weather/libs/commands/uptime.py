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


@command('uptime', direct=True)
def cmd_uptime(target: str | None = None) -> CommandResponse:
	uptime = None
	try:
		with open('/proc/uptime', 'r') as f:
			uptime = float(f.read().split()[0])
	except FileNotFoundError:
		logging.error('Could not read uptime')
		return CommandResponseError('Could not read uptime')

	if uptime > 86400:
		days = int(uptime / 86400)
		hours = int((uptime - (days * 86400)) / 3600)
		return CommandResponseSuccess(f"Uptime: {days} days, {hours} hours")
	if uptime > 3600:
		hours = int(uptime / 3600)
		uptime = round(uptime % 3600)
		return CommandResponseSuccess(f"Uptime: {hours} hours, {uptime} seconds")

	return CommandResponseSuccess(f"Uptime: {uptime} seconds")
