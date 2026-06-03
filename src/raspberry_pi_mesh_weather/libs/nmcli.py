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

import subprocess

def _lookup(key):
	try:
		# Runs 'nmcli -t -f active,{KEY} dev wifi'
		# This filters for only the active connection and shows the SSID
		cmd = ["nmcli", "-t", "-f", f"active,{key}", "dev", "wifi"]
		output = subprocess.check_output(cmd, text=True)

		for line in output.strip().split('\n'):
			if line.startswith("yes:"):
				return line.split(":")[1]
		return None
	except Exception as e:
		print(f"Error: {e}")
		return None


def get_ssid():
	return _lookup("ssid")


def get_bars():
	return _lookup("bars")


def get_rate():
	return _lookup("rate")


def get_frequency():
	return _lookup("freq")