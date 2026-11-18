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
# You should have received a copy of a GNU Affero General Public License
# along with this program.  If not, see <https://gnu.org>.
#
import time

from .handler import command, CommandResponse, CommandResponseNoData, CommandResponseSuccess
from raspberry_pi_mesh_weather.libs.config import config
from raspberry_pi_mesh_weather.libs import sun


def _relative_label(ts: float, now: float) -> str:
	"""
	Human-readable relative label for a sun event relative to `now` (both
	epoch seconds): 'in 1h 19m' for a future event, '8h 46m ago' for a past
	one. Rounded to the nearest minute.
	"""
	delta = abs(now - ts)
	if delta < 30:
		return 'now'
	minutes = round(delta / 60)
	hours, mins = divmod(minutes, 60)
	text = (f'{hours}h {mins}m' if hours and mins else (f'{hours}h' if hours else f'{mins}m'))
	return f'in {text}' if ts > now else f'{text} ago'


@command('sun', direct=True, group=True)
def cmd_sun(target: str | None = None) -> CommandResponse:
	"""
	Report today's sunrise and sunset times.
	What time is sunrise
	What time is sunset
	Sunset time
	When does the sun rise
	When will it go dark
	"""
	now = time.time()
	sunrise = sun.get_sunrise()
	sunset = sun.get_sunset()

	lines = []
	if sunrise is not None:
		lines.append(f'Sunrise {sun.format_time(sunrise)} ({_relative_label(sunrise, now)})')
	if sunset is not None:
		lines.append(f'Sunset {sun.format_time(sunset)} ({_relative_label(sunset, now)})')

	if not lines:
		return CommandResponseNoData('Sorry, but no sunrise/sunset available')

	label = config.location.label
	header = f'Sun in {label}:' if label else 'Sun here:'
	return CommandResponseSuccess(header + '\n' + '\n'.join(lines))
