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
from datetime import datetime
from time import time

from raspberry_pi_mesh_weather.libs import open_weather_map


def get_sunrise():
	"""
	Get the next sunrise as an epoch-second timestamp.

	There is no local sunrise sensor, so this is always service-derived.

	:return: sunrise epoch (local time for the location), or None if unavailable.
	"""
	conditions = open_weather_map.get_current_conditions()
	return conditions.get('sunrise') if conditions else None


def get_sunset():
	"""
	Get the next sunset as an epoch-second timestamp.

	There is no local sunset sensor, so this is always service-derived.

	:return: sunset epoch (local time for the location), or None if unavailable.
	"""
	conditions = open_weather_map.get_current_conditions()
	return conditions.get('sunset') if conditions else None


def get_next_sun_event(now: float | None = None) -> dict | None:
	"""
	Determine which sun event (sunrise or sunset) happens next, relative to
	`now` (epoch seconds, defaulting to the current wall clock).

	The OpenWeatherMap current-conditions response only carries today's sunrise
	and sunset, so when both have already passed (the evening) there is no
	future event to report.

	:return: {'name': 'sunrise'|'sunset', 'dt': <epoch>} for the first event
			after `now`, else None (data unavailable or both events already past).
	"""
	if now is None:
		now = time()

	events = []
	sunrise = get_sunrise()
	sunset = get_sunset()
	if sunrise is not None and sunrise > now:
		events.append(('sunrise', sunrise))
	if sunset is not None and sunset > now:
		events.append(('sunset', sunset))
	if not events:
		return None
	# The earliest event that is still ahead of now is the next one.
	events.sort(key=lambda e: e[1])
	return {'name': events[0][0], 'dt': events[0][1]}


def format_time(ts: float) -> str:
	"""
	Format an epoch-second timestamp as a short local time-of-day string.

	'12:13 PM', '8:18 PM', '12:00 AM'.

	:param ts: epoch seconds.
	:return: the time-of-day string.
	"""
	dt = datetime.fromtimestamp(ts)
	period = 'AM' if dt.hour < 12 else 'PM'
	hour12 = dt.hour % 12 or 12
	return f'{hour12}:{dt.minute:02d} {period}'
