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


def get_humidity():
	if os.path.exists('/tmp/humidity.txt'):
		with open('/tmp/humidity.txt', 'r') as f:
			val = f.read()
			return None if val == '' else float(val)
	else:
		return None


def set_humidity(humidity):
	with open('/tmp/humidity.txt', 'w') as f:
		f.write(str(humidity))
