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

from .handler import command, CommandResponse, CommandResponseSuccess
from raspberry_pi_mesh_weather.libs.nmcli import get_bars, get_rate, get_ssid, get_frequency
from raspberry_pi_mesh_weather.libs.get_local_ip import get_local_ip


@command('net', direct=True, auth=True)
def cmd_net(target: str | None = None):
	"""
	Report the device's network details: local IP, SSID, signal bars,
	link rate and frequency.
	What is the network configuration
	Network details
	Wi-Fi stats
	What is the local IP
	"""
	ip = get_local_ip()
	ssid = get_ssid()
	bars = get_bars()
	rate = get_rate()
	freq = get_frequency()
	return CommandResponseSuccess(f"IP: {ip}\nSSID: {ssid}\nBars: {bars}\nRate: {rate}\nFreq: {freq}")
