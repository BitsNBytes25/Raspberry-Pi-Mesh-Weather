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
import os
import sys
import time
import argparse
import logging
from datetime import datetime
from dotenv import load_dotenv
from meshcore import MeshCore, EventType

from .libs.home_assistant import push_mesh_node_to_map
from .libs.humidity import get_humidity
from .libs.mesh_contacts import store_contacts
from .libs.pressure import get_pressure, get_pressure_change
from .libs.temperature import get_temperature
from .libs.weather_forecast import WeatherForecast
from .libs.weather_alerts import get_alerts


def get_heat_index(temp_c, humidity):
	# Heat Index is generally not applicable below 26.7C
	if temp_c < 26.7:
		return temp_c

	# Convert Celsius to Fahrenheit for the formula
	T = (temp_c * 9/5) + 32
	R = humidity

	# Constants for the Rothfusz regression
	hi_f = (-42.379 + (2.04901523 * T) + (10.14333127 * R) +
			(-0.22475541 * T * R) + (-0.00683783 * T**2) +
			(-0.05481717 * R**2) + (0.00122874 * T**2 * R) +
			(0.00085282 * T * R**2) + (-0.00000199 * T**2 * R**2))

	# Convert back to Celsius
	return (hi_f - 32) * 5/9


class WatchMeshcore:
	def __init__(self):
		load_dotenv()

		self.radio = None
		self.mesh_port = os.getenv('MESH_PORT', '/dev/ttyUSB0')
		self.ha_url = os.getenv('HA_URL')
		self.ha_token = os.getenv('HA_TOKEN')
		self.openweathermap_api_key = os.getenv('OPENWEATHERMAP_API_KEY')
		self.location_lat = os.getenv('LOCATION_LAT')
		self.location_lon = os.getenv('LOCATION_LON')
		self.location_label = os.getenv('LOCATION_LABEL')
		self.weather_channel = 1

	def cmd_ping(self):
		return 'pong'

	def cmd_uptime(self):
		uptime = None
		try:
			with open('/proc/uptime', 'r') as f:
				uptime = float(f.read().split()[0])
		except FileNotFoundError:
			logging.error('Could not read uptime')
			return 'Could not read uptime'

		if uptime > 86400:
			days = int(uptime / 86400)
			hours = int((uptime - (days * 86400)) / 3600)
			return f"Uptime: {days} days, {hours} hours"
		if uptime > 3600:
			hours = int(uptime / 3600)
			uptime = round(uptime % 3600)
			return f"Uptime: {hours} hours, {uptime} seconds"

		return f"Uptime: {uptime} seconds"

	def cmd_cpu(self):
		temp = None
		try:
			with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
				temp = float(f.read()) / 1000
		except FileNotFoundError:
			logging.error('Could not read CPU temperature')

		load = os.getloadavg()
		load = round(load[1])
		if temp is not None:
			return f"CPU: {load}% load and {temp}°C"
		else:
			return f"CPU: {load}% load"

	def cmd_temp(self):
		temp = get_temperature()
		humidity = get_humidity()

		if temp is None:
			# Temperature not available.
			return 'Sorry, but no temperature is available right now.'
		elif humidity is None:
			# Temperature is, but humidity is not.
			fake_temp = round(temp * 1.8 + 32, 1)
			real_temp = round(temp, 1)
			return f"Current temperature here is {real_temp}°C ({fake_temp}°F)"
		else:
			fake_temp = int(temp * 1.8 + 32)
			real_temp = int(temp)
			temps = f"{real_temp}°C ({fake_temp}°F)"
			pressure_change = get_pressure_change()

			if real_temp < 1:
				return f"🥶 FREEZING! It's {temps} - Just stay home and get some hot chocolate!"

			if real_temp < 10:
				return f"🧊 It's currently {temps} - Stay inside or bundle up!"

			if 10 <= real_temp < 18:
				if humidity > 80:
					return f"☔ Damp and chilly, it's currently {temps}. Grab a waterproof coat."

				if pressure_change == -1:
					return f"☁️ A bit chilly at {temps} and rain may be on the horizon."
				if pressure_change == 1:
					return f"☀️ A bit chilly at {temps} but should be sunny."
				return f"A bit chilly right now at {temps}."

			if 18 <= real_temp <= 24:
				if pressure_change == 0 or pressure_change == 1:
					if 30 <= humidity <= 60:
						return f"☀️ Perfectly comfortable at {temps}.  Go out for a nice walk."
					if humidity > 60:
						return f"☁️ It's a comfortable {temps} but is rather sticky."
				else:
					if 30 <= humidity <= 60:
						return f"☁️ Perfectly comfortable at {temps} but it may storm soon."
					if humidity > 60:
						return f"☔ It's a comfortable {temps} but is rather wet out there."

			if 24 < real_temp <= 29:
				hi = int(get_heat_index(real_temp, humidity))
				fake_hi = int(hi * 1.8 + 32)
				feels_like = f"{hi}°C ({fake_hi}°F)"

				if pressure_change == -1:
					return f"☔ It's a hot and muggy {temps} and feels like {feels_like}.  Expect storms soon."
				if hi > 32 and humidity > 70:
					return f"🥵 It's a hot and muggy {temps} but feels like {feels_like}.  Take water & limit activity."
				return f"☀️ Warm and sunny at {temps}. Enjoy the heat!"

			if real_temp > 29:
				hi = int(get_heat_index(real_temp, humidity))
				fake_hi = int(hi * 1.8 + 32)
				if hi > 34 and humidity > 70:
					feels_like = f"{hi}°C ({fake_hi}°F"
					return f"🔥 It's an oppressive {temps} & feels like {feels_like}. STAY SAFE AND HYDRATED!"

				if humidity <= 30:
					return f"☀️ Hot and sunny at {temps} but very low humidity.  Enjoy the heat!"

				if pressure_change == -1:
					return f"☀️ Hot and sunny at {temps} right now, but enjoy it while it lasts.  Storms may be on the horizon"

				return f"☀️ Hot and sunny at {temps}. Enjoy the heat!"

			return temps

	def cmd_pressure(self):
		pressure = get_pressure()
		pressure_change = get_pressure_change()

		if pressure is None:
			return 'Sorry, but no pressure is available right now.'

		pressure = round(pressure, 2)

		if pressure_change == 1:
			return f"Pressure has rose to {pressure}hPa!  Expect sunny weather."

		if pressure_change == -1:
			return f"Pressure has fallen to {pressure}hPa!  Expect rainy weather."

		return f"Pressure is a stable {pressure}hPa"

	def cmd_daily_forecast(self) -> str:
		"""
		Fetches the daily weather forecast and broadcasts it over the mesh network.
		"""

		if self.openweathermap_api_key is None or self.openweathermap_api_key == '':
			logging.error('No API key set for openweathermap.org, no forecast data available')
			return ''

		if self.location_lat is None or self.location_lat == '':
			logging.error('No latitude set, unable to pull forecast data.')
			return ''

		if self.location_lon is None or self.location_lon == '':
			logging.error('No longitude set, unable to pull forecast data.')
			return ''

		if self.location_label is None or self.location_label == '':
			header = 'Daily Forecast'
		else:
			header = f'Today for {self.location_label}'

		logging.debug('--- Running Daily Weather Forecast Fetch ---')
		try:
			# Initialize the weather client (it will read OPENWEATHERMAP_API_KEY)
			weather_client = WeatherForecast(self.openweathermap_api_key, self.location_lat, self.location_lon)
			forecast = weather_client.get_daily_forecast()

			if not forecast:
				print('Weather Forecast: Failed to retrieve data.')
				return ''

			low_f = round(forecast['low_temp'] * 1.8 + 32, 0)
			high_f = round(forecast['high_temp'] * 1.8 + 32, 0)

			# Format the message for broadcasting
			message = (
				f"{header}:\n{forecast['general_outlook']}\nLow/High: {forecast['low_temp']} / {forecast['high_temp']}°C\n({low_f} / {high_f}°F)"
			)
			return message
		except Exception as e:
			error_msg = f"Daily Weather: An error occurred during forecast fetching/broadcasting: {e}"
			print(f"Weather Forecast Error: {e}")
			return error_msg

	def cmd_alerts(self):
		if self.location_lat is None or self.location_lat == '':
			logging.error('No latitude set, unable to pull forecast data.')
			return ''

		if self.location_lon is None or self.location_lon == '':
			logging.error('No longitude set, unable to pull forecast data.')
			return ''

		if self.location_label is None or self.location_label == '':
			header = 'Weather Alerts'
		else:
			header = f'Alerts for {self.location_label}'

		logging.debug('--- Running Alerts Fetch ---')
		try:
			alerts = get_alerts(self.location_lat, self.location_lon)

			if len(alerts) == 0:
				return 'No weather alerts at this time.'

			return f"{header}:\n" + '\n'.join(alerts)
		except Exception as e:
			error_msg = f"Weather Alerts: An error occurred during alert fetching/broadcasting: {e}"
			print(f"Weather Alerts Error: {e}")
			return error_msg

	# --- Daily Forecast Integration ---
	async def run_daily_forecast(self):
		"""Runs the forecast fetch and broadcasts it."""

		message = self.cmd_daily_forecast()
		if message == '':
			return

		# Broadcast to all nodes (or a specific group if MESH_PORT is set)
		await self.radio.commands.send_chan_msg(self.weather_channel, message)

	async def run_alerts(self):
		if self.location_lat is None or self.location_lat == '':
			logging.error('No latitude set, unable to pull forecast data.')
			return

		if self.location_lon is None or self.location_lon == '':
			logging.error('No longitude set, unable to pull forecast data.')
			return

		if self.location_label is None or self.location_label == '':
			header = 'Weather Alerts'
		else:
			header = f'Alerts for {self.location_label}'

		logging.debug('--- Running Alerts Fetch ---')
		try:
			alerts = get_alerts(self.location_lat, self.location_lon)

			if len(alerts) == 0:
				# No alerts, just return without broadcasting anything
				return

			msg = f"{header}:\n" + '\n'.join(alerts)
			# Broadcast to all nodes (or a specific group if MESH_PORT is set)
			await self.radio.commands.send_chan_msg(self.weather_channel, msg)
		except Exception as e:
			error_msg = f"Weather Alerts: An error occurred during alert fetching/broadcasting: {e}"
			logging.error(error_msg)

	async def run_channel_message(self, event):
		"""
		Handle messages received on a channel;
		these are generally public and replies are sent out to the entire channel
		:param event:
		:return:
		"""

		channel = event.payload['channel_idx']
		text = event.payload.get('text', '')

		if channel == self.weather_channel:
			# 1 is the weather channel, process it!
			sensor = None

			if ':' in text:
				text = text.split(':', 1)[1].strip().lower()

			if text == '!temp' or text == '!temperature':
				sensor = self.cmd_temp()
			elif text == '!humidity':
				humidity = get_humidity()
				if humidity is None:
					sensor = 'Sorry, but no humidity available'
				else:
					sensor = 'Current humidity here is %s%%' % round(humidity, 1)
			elif text == '!pres' or text == '!pressure':
				sensor = self.cmd_pressure()
			elif text == '!all':
				temp = get_temperature()
				humidity = get_humidity()
				pressure = get_pressure()
				sensors = []

				if temp is not None:
					sensors.append('Temp: %s°C' % round(temp, 1))
				if humidity is not None:
					sensors.append('Humi: %s%%' % round(humidity, 1))
				if pressure is not None:
					sensors.append('Pres: %shPa' % round(pressure, 1))

				if len(sensors) > 0:
					sensor = 'Current conditions here:\n' + ' | '.join(sensors)
			elif text == '!forecast':
				sensor = self.cmd_daily_forecast()
			elif text == '!alerts':
				sensor = self.cmd_alerts()

			if sensor is not None:
				await self.radio.commands.send_chan_msg(channel, sensor)

		else:
			logging.debug(f"Received message on channel {channel}: {text}")

	def run_event(self, event):
		from pprint import pprint
		pprint(event)

	async def run_direct_message(self, event):

		message = None
		text = event.payload.get('text', '').lower()
		target = event.payload.get('pubkey_prefix')

		if text == 'help':
			message = 'Available commands:\n'
			commands = ['ping', 'uptime', 'cpu', 'temp', 'pres', 'wake', 'forecast', 'alerts']
			message += ' | '.join(commands)
		elif text == 'ping':
			message = self.cmd_ping()
		elif text == 'uptime':
			message = self.cmd_uptime()
		elif text == 'cpu':
			message = self.cmd_cpu()
		elif text == 'temp' or text == 'temperature':
			message = self.cmd_temp()
		elif text == 'pres' or text == 'pressure':
			message = self.cmd_pressure()
		elif text == 'wake':
			# Write a file to wake the device up
			with open('/tmp/wake', 'w') as f:
				f.write('wake')
			message = 'Device display should wake up shortly.'
		elif text == 'forecast':
			message = self.cmd_daily_forecast()
		elif text == 'alerts':
			message = self.cmd_alerts()

		if message is None:
			message = 'Sorry, I don\'t understand that command.  Try "help" for a list of commands.'

		result = await self.radio.commands.send_msg(target, message)

		if result.type == EventType.ERROR:
			logging.error(f"Failed to send: {result.payload['reason']}")
		else:
			logging.debug(f"Reply sent to {target}")

	async def _setup_radio(self):
		logging.debug(f"Connecting Meshcore via serial port {self.mesh_port}")
		try:
			self.radio = await MeshCore.create_serial(self.mesh_port, 115200)
		except FileNotFoundError:
			logging.error(f"Mesh radio not found on port {self.mesh_port}.  Please check your settings.")
			return

		# Some devices allow setting this via custom variables or specific commands
		# This ensures discovered nodes are added to memory automatically
		logging.debug('Ensuring contacts are added automatically...')
		await self.radio.commands.set_custom_var('auto_add_contacts', '1')

		logging.debug('Ensuring contacts are added...')
		await self.radio.ensure_contacts()

		# Auto-fetch new messages
		logging.debug('Starting auto-message fetching...')
		await self.radio.start_auto_message_fetching()

		# Subscribe to the "#weather" channel
		logging.debug('Subscribing to channel #weather...')
		await self.radio.commands.set_channel(self.weather_channel, '#weather')

		# Checks ALL events
		# radio.subscribe(None, handle_event)

		# radio.subscribe(EventType.CONTACT_MSG_RECV, handle_message)

		logging.debug('Subscribing to channel messages...')
		self.channel_subscription = self.radio.subscribe(EventType.CHANNEL_MSG_RECV, self.run_channel_message)
		self.direct_subscription = self.radio.subscribe(EventType.CONTACT_MSG_RECV, self.run_direct_message)

		logging.debug('Mesh Radio Ready!')

	async def _shutdown_radio(self):
		if self.radio is None:
			return

		await self.radio.stop_auto_message_fetching()
		self.radio.unsubscribe(self.channel_subscription)
		self.radio.unsubscribe(self.direct_subscription)
		self.radio.stop()

		self.radio = None

	async def run(self):
		# Timers in seconds
		LOCAL_INTERVAL = 900  # 15 minutes
		FLOOD_INTERVAL = 10800  # 3 hours
		ALERT_INTERVAL = 1800  # 30 minutes

		last_local = 0
		last_flood = 0
		last_daily = 0
		last_alerts = 0

		while True:
			if self.radio is None:
				await self._setup_radio()

			if self.radio is None:
				# Will try to reconnect in another minute
				await asyncio.sleep(60)
				continue

			try:
				now = time.time()
				hour = datetime.now().hour

				# Update Peer/Repeater list
				contacts = await self.radio.commands.get_contacts()
				if contacts.type != EventType.ERROR:
					# Store discovered contacts in a temp file so it can be used by other scripts.
					raw_contacts = list(contacts.payload.values())
					store_contacts(raw_contacts)

					if self.ha_url and self.ha_token != '':
						# Push these to Home Assistant too!
						for contact in raw_contacts:
							push_mesh_node_to_map(self.ha_url, self.ha_token, contact)

				if now - last_flood > FLOOD_INTERVAL:
					# Send Flood (Network-wide) Advert
					logging.debug('Sending flood advert...')
					await self.radio.commands.send_advert(True)
					last_flood = now
					last_local = now
				elif now - last_local > LOCAL_INTERVAL:
					# Send Zero-Hop (Local) Advert
					logging.debug('Sending local advert...')
					await self.radio.commands.send_advert(False)
					last_local = now

				# --- Weather Check Logic ---
				# Daily forecast check, runs between 6 and 7 in the morning
				if 6 <= hour < 7 and now - last_daily > FLOOD_INTERVAL:
					await self.run_daily_forecast()
					last_daily = now

				if now - last_alerts > ALERT_INTERVAL:
					await self.run_alerts()
					last_alerts = now

				await asyncio.sleep(60)
			except KeyboardInterrupt:
				logging.info("Keyboard interrupt received. Exiting...")
				await self._shutdown_radio()
				sys.exit(0)


def main():
	parser = argparse.ArgumentParser(description="Meshcore Watcher Application")

	# Add the --debug flag
	# action="store_true" means it becomes True if present, and False if not
	parser.add_argument(
		'--debug',
		action='store_true',
		help='Enable debug mode with verbose logging'
	)

	parser.add_argument(
		'--test',
		action='store_true',
		help='Run all supported commands and exit without connecting to the mesh network'
	)

	args = parser.parse_args()

	if args.debug:
		logging.getLogger().setLevel(logging.DEBUG)
		logging.basicConfig(level=logging.DEBUG)
		logging.debug("Debug mode enabled")

	watcher = WatchMeshcore()

	if args.test:
		print('ping: ' + watcher.cmd_ping())
		print('uptime: ' + watcher.cmd_uptime())
		print('cpu: ' + watcher.cmd_cpu())
		print('temp: ' + watcher.cmd_temp())
		print('pres: ' + watcher.cmd_pressure())
		print('forecast: ' + watcher.cmd_daily_forecast())
		print('alerts: ' + watcher.cmd_alerts())
		sys.exit(0)

	asyncio.run(watcher.run())
