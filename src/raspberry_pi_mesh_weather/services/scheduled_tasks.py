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

import asyncio
import logging
from datetime import datetime

from raspberry_pi_mesh_weather.libs.commands import get_command
from raspberry_pi_mesh_weather.libs.config import config
from raspberry_pi_mesh_weather.libs.weather_alerts import get_new_alerts
from raspberry_pi_mesh_weather.services.service import Service


class ScheduledTasks(Service):
	"""
	Shared scheduler for recurring tasks that are independent of a specific radio.

	Holds a reference to the mesh radio and broadcasts results to it.  The radios
	only implement how they physically transmit (via `broadcast`), so every task
	here can work with either MeshCore or Meshtastic unchanged.

	Scheduled jobs: weather alerts (checked every 5 minutes), the daily
	forecast (6-9 AM and 4-6 PM), and current weather (10 AM-4 PM).  Alerts
	are checked first each tick so that an alert broadcast takes priority over
	the other jobs.  This is also the home for any additional jobs
	(sunrise/sunset, ...).
	"""

	# Timers in seconds
	HOURLY_INTERVAL = 3600  # 1 hour
	ALERT_INTERVAL = 300  # 5 minutes
	SLEEP_SECONDS = 60  # 1 minute poll

	def __init__(self, sender, clock=None):
		super().__init__()
		self.sender = sender  # the mesh radio that transmits the results
		self._clock = clock or datetime.now  # injectable for testing

		self._current_timestamp = self._clock().now().timestamp() # Kept up to date each tick
		self._last_forecast = 0
		self._last_current = 0
		self._last_alert = 0

	async def run_daily_forecast(self) -> bool:
		"""
		Fetch the next forecast entries and broadcast them over the mesh.

		Limited to run only once per hour.
		"""
		if (self._current_timestamp - self._last_forecast) < self.HOURLY_INTERVAL:
			# Last forecast was sent within 1 hour, do not spam the network
			return False

		cmd = get_command('!forecast')
		if cmd is None:
			return False

		result = cmd(None)
		if result.success and result.has_data:
			# Command successfully completed, send the broadcast and make a log of when it was sent
			await self.sender.broadcast(result.message)
			self._last_forecast = self._current_timestamp
			return True
		return False

	async def run_current_weather(self) -> bool:
		"""
		Fetch current weather via the 'all' command

		Limited to run only once per hour.
		"""
		if (self._current_timestamp - self._last_current) < self.HOURLY_INTERVAL:
			# Last current was sent within 1 hour, do not spam the network
			return False

		cmd = get_command('!all')
		if cmd is None:
			return False

		result = cmd(None)
		if result.success and result.has_data:
			# Command successfully completed, send the broadcast and make a log of when it was sent
			await self.sender.broadcast(result.message)
			self._last_current = self._current_timestamp
			return True
		return False

	async def run_alerts(self) -> bool:
		"""
		Fetch new weather alerts and broadcast them over the mesh.

		Limited to run only once per 5 minutes.
		"""
		if (self._current_timestamp - self._last_alert) < self.ALERT_INTERVAL:
			# Last alert check was recent, do not hammer the API
			return False

		lat = config.location.lat
		lon = config.location.lon
		if lat is None or lon is None:
			return False

		logging.debug('--- Running Scheduled Alerts Fetch ---')
		new_alerts = get_new_alerts(lat, lon)
		if not new_alerts:
			# No new alerts for this region
			return False

		# Only ever-unseen tracked alerts: dedup lives in weather_alerts.
		alerts = '\n'.join(f"{alert['icon']}  {alert['title']}" for alert in new_alerts)

		# Command successfully completed, send the broadcast and make a log of when it was sent
		await self.sender.broadcast(alerts)
		self._last_alert = self._current_timestamp
		return True

	async def load(self) -> bool:
		# The sender (radio) is already loaded by the caller; nothing else to init.
		return True

	async def test(self):
		# Run a single forecast to verify the fetch + broadcast path works.
		pass

	async def run(self):
		while self.running:
			now = self._clock()
			hour = now.hour
			self._current_timestamp = now.timestamp()
			sent = False # Only send one broadcast per tick

			# Alerts first: an alert broadcast preempts the other jobs for
			# this tick.
			if not sent and await self.run_alerts():
				sent = True

			# Schedule for automated tasks (skipped if an alert already used
			# this tick's broadcast slot)
			if not sent:
				if 6 <= hour <= 9:
					# Run the forecast between hours of 6a-9a
					if await self.run_daily_forecast():
						sent = True
				elif 10 <= hour <= 15:
					# Provide current weather during the day
					if await self.run_current_weather():
						sent = True
				elif 16 <= hour <= 18:
					# Run the forecast between hours of 4p-6p
					if await self.run_daily_forecast():
						sent = True

			await asyncio.sleep(self.SLEEP_SECONDS)
