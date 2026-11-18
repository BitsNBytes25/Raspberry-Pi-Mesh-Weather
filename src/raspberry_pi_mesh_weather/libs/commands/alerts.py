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

from .handler import command, CommandResponse, CommandResponseError, CommandResponseNoData, CommandResponseSuccess
from raspberry_pi_mesh_weather.libs.config import config
from raspberry_pi_mesh_weather.libs.weather_alerts import get_alerts


def build_alerts_response(alerts) -> CommandResponse:
	"""
	Build a CommandResponse from a list of alert records.

	Uses config.location.label for the header. Returns a
	CommandResponseNoData when there are no alerts; otherwise a
	CommandResponseSuccess listing each record's icon and title, one per line.
	"""
	if not alerts:
		return CommandResponseNoData('No weather alerts at this time.')

	if config.location.label == '':
		header = 'Weather Alerts'
	else:
		header = f'Alerts for {config.location.label}'

	return CommandResponseSuccess(
		f"{header}:\n" + '\n'.join(f"{alert['icon']}  {alert['title']}" for alert in alerts)
	)


@command('alerts', direct=True, group=True)
def cmd_alerts(target: str | None = None) -> CommandResponse:
	lat = config.location.lat
	lon = config.location.lon

	if lat is None:
		logging.error('No latitude set, unable to pull forecast data.')
		return CommandResponseError('No latitude set, unable to pull weather alerts.')

	if lon is None:
		logging.error('No longitude set, unable to pull forecast data.')
		return CommandResponseError('No longitude set, unable to pull weather alerts.')

	logging.debug('--- Running Alerts Fetch ---')
	try:
		# Only ever-unseen tracked alerts: dedup lives in weather_alerts.
		all_alerts = get_alerts(lat, lon)

		if not all_alerts:
			return CommandResponseNoData('No weather alerts at this time.')

		return CommandResponseSuccess(
			'\n'.join(f"{alert['icon']}  {alert['title']}" for alert in all_alerts)
		)
	except Exception as e:
		error_msg = f"Weather Alerts: An error occurred during alert fetching/broadcasting: {e}"
		print(f"Weather Alerts Error: {e}")
		return CommandResponseError(error_msg)
