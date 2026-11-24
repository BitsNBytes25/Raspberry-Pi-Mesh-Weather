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
from raspberry_pi_mesh_weather.libs.icon_map import STANDARD_ICON_NAMES, get_icon


@command('icons', direct=True)
def cmd_icons(target: str | None = None) -> CommandResponse:
	"""
	List the weather glyphs the service can render on mesh devices, so the
	sender can verify which icons their device displays.
	Which icons can the service show
	Show the weather icons
	Which glyphs render
	Icon test
	"""
	icons = ' '.join(get_icon(name) for name in STANDARD_ICON_NAMES)
	return CommandResponseSuccess(icons)
