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
from datetime import datetime

from raspberry_pi_mesh_weather.libs.commands import get_command
from raspberry_pi_mesh_weather.services.service import Service


class ScheduledTasks(Service):
	"""
	Shared scheduler for recurring tasks that are independent of a specific radio.

	Holds a reference to the mesh radio and broadcasts results to it.  The radios
	only implement how they physically transmit (via `broadcast`), so every task
	here can work with either MeshCore or Meshtastic unchanged.

	Currently only the daily forecast is scheduled, but this is the home for the
	other hourly jobs (current weather during the day, sunrise/sunset, ...).
	"""

	# Timers in seconds
	HOURLY_INTERVAL = 3600  # 1 hour
	SLEEP_SECONDS = 60  # 1 minute poll

	def __init__(self, sender, clock=None):
		super().__init__()
		self.sender = sender  # the mesh radio that transmits the results
		self._clock = clock or datetime.now  # injectable for testing

		self._current_timestamp = self._clock().now().timestamp() # Kept up to date each tick
		self._last_forecast = 0

	async def run_daily_forecast(self):
		"""
		Fetch the next forecast entries and broadcast them over the mesh.

		Limited to run only once per hour.
		"""
		if (self._current_timestamp - self._last_forecast) < self.HOURLY_INTERVAL:
			# Last forecast was sent within 1 hour, do not spam the network
			return

		cmd = get_command('!forecast')
		if cmd is None:
			return

		result = cmd(None)
		if result.success and result.has_data:
			# Command successfully completed, send the broadcast and make a log of when it was sent
			await self.sender.broadcast(result.message)
			self._last_forecast = self._current_timestamp

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

			if 6 <= hour <= 9 or 16 <= hour <= 18:
				# Run the forecast between hours of 6a-9a and 4p-6p
				await self.run_daily_forecast()

			await asyncio.sleep(self.SLEEP_SECONDS)
