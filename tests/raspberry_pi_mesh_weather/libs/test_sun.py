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
from datetime import datetime, timezone

from raspberry_pi_mesh_weather.libs import sun as sun_lib

# Columbus current-conditions fixture gives (UTC) 12:13 PM sunrise and
# 10:18 PM sunset, with the current timestamp at 9:00 PM.
_SUNRISE = 1794485621
_SUNSET = 1794521926
_NOW = 1794517200

_utc = timezone.utc


def _patch_time(mocker):
	"""
	Pin the datetime class used by the sun module to UTC so that
	format_time output is deterministic and independent of the machine's
	timezone.
	"""

	class _FakeDatetime(datetime):
		@classmethod
		def fromtimestamp(cls, ts, *args, **kwargs):
			return datetime.fromtimestamp(ts, tz=_utc)

	mocker.patch.object(sun_lib, 'datetime', _FakeDatetime)


def _patch_owm(mocker, conditions):
	"""
	Patch the shared OWM current-conditions accessor that sun.py reads.
	"""
	mocker.patch.object(sun_lib.open_weather_map, 'get_current_conditions',
						return_value=conditions)


# --- getters -----------------------------------------------------------


def test_get_sunrise_reads_owm(mocker):
	_patch_time(mocker)
	_patch_owm(mocker, {'sunrise': _SUNRISE, 'sunset': _SUNSET})
	assert sun_lib.get_sunrise() == _SUNRISE


def test_get_sunset_reads_owm(mocker):
	_patch_time(mocker)
	_patch_owm(mocker, {'sunrise': _SUNRISE, 'sunset': _SUNSET})
	assert sun_lib.get_sunset() == _SUNSET


def test_get_sunrise_none_when_no_conditions(mocker):
	_patch_owm(mocker, None)
	assert sun_lib.get_sunrise() is None
	assert sun_lib.get_sunset() is None


def test_get_sunrise_none_when_missing_key(mocker):
	_patch_owm(mocker, {'temp': 12.0})
	assert sun_lib.get_sunrise() is None
	assert sun_lib.get_sunset() is None


# --- get_next_sun_event ------------------------------------------------


def test_get_next_sun_event_daytime_returns_sunset(mocker):
	_patch_time(mocker)
	_patch_owm(mocker, {'sunrise': _SUNRISE, 'sunset': _SUNSET})
	result = sun_lib.get_next_sun_event(now=_NOW)

	# 9:00 PM is between the 12:13 PM sunrise and the 10:18 PM sunset.
	assert result == {'name': 'sunset', 'dt': _SUNSET}


def test_get_next_sun_event_pre_dawn_returns_sunrise(mocker):
	_patch_time(mocker)
	_patch_owm(mocker, {'sunrise': _SUNRISE, 'sunset': _SUNSET})
	result = sun_lib.get_next_sun_event(now=_SUNRISE - 5621)

	# ~58 minutes before the 12:13 PM sunrise -> sunrise is next.
	assert result == {'name': 'sunrise', 'dt': _SUNRISE}


def test_get_next_sun_event_evening_returns_none(mocker):
	_patch_time(mocker)
	_patch_owm(mocker, {'sunrise': _SUNRISE, 'sunset': _SUNSET})
	result = sun_lib.get_next_sun_event(now=_SUNSET + 3074)

	# 11:10 PM, after both today's events have passed -> no next event.
	assert result is None


def test_get_next_sun_event_none_when_no_conditions(mocker):
	_patch_owm(mocker, None)
	assert sun_lib.get_next_sun_event(now=_NOW) is None


def test_get_next_sun_event_earliest_wins(mocker):
	_patch_time(mocker)
	_patch_owm(mocker, {'sunrise': _SUNRISE, 'sunset': _SUNSET})
	# Now is before both events; the earlier one (sunrise) is returned.
	assert sun_lib.get_next_sun_event(now=_SUNRISE - 600) == {'name': 'sunrise', 'dt': _SUNRISE}
	# Now is after sunrise but before sunset; the next one (sunset) is returned.
	assert sun_lib.get_next_sun_event(now=_NOW) == {'name': 'sunset', 'dt': _SUNSET}


# --- format_time -------------------------------------------------------


def test_format_time_pm(mocker):
	_patch_time(mocker)
	assert sun_lib.format_time(_SUNRISE) == '12:13 PM'
	assert sun_lib.format_time(_SUNSET) == '10:18 PM'
	assert sun_lib.format_time(_NOW) == '9:00 PM'


def test_format_time_midnight(mocker):
	_patch_time(mocker)
	utc_midnight = int(datetime(2026, 11, 12, 0, 0, tzinfo=_utc).timestamp())
	utc_one_05 = int(datetime(2026, 11, 12, 1, 5, tzinfo=_utc).timestamp())
	assert sun_lib.format_time(utc_midnight) == '12:00 AM'
	assert sun_lib.format_time(utc_one_05) == '1:05 AM'
