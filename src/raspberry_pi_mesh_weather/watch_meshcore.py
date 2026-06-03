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
from .libs.nmcli import get_bars, get_rate, get_ssid, get_frequency
from .libs.get_local_ip import get_local_ip


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


class CommandResponse:
	"""
	Simple wrapper for command responses,
	useful to know between "" means an error or
	"" means just no data but successful.
	"""
	def __init__(self, success=True, has_data=True, message=None):
		self.success = success
		self.has_data = has_data
		self.message = message


class CommandResponseError(CommandResponse):
	def __init__(self, message=None):
		CommandResponse.__init__(self, False, False, message)


class CommandResponseSuccess(CommandResponse):
	def __init__(self, message=None):
		CommandResponse.__init__(self, True, True, message)


class CommandResponseNoData(CommandResponse):
	def __init__(self, message=None):
		CommandResponse.__init__(self, True, False, message)


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
		auth_radios = os.getenv('AUTH_RADIOS')
		if auth_radios is not None and auth_radios != '':
			self.auth_radios = auth_radios.split(',')
		else:
			self.auth_radios = []

	def cmd_ping(self) -> CommandResponse:
		return CommandResponseSuccess('pong')

	def cmd_uptime(self) -> CommandResponse:
		uptime = None
		try:
			with open('/proc/uptime', 'r') as f:
				uptime = float(f.read().split()[0])
		except FileNotFoundError:
			logging.error('Could not read uptime')
			return CommandResponseError('Could not read uptime')

		if uptime > 86400:
			days = int(uptime / 86400)
			hours = int((uptime - (days * 86400)) / 3600)
			return CommandResponseSuccess(f"Uptime: {days} days, {hours} hours")
		if uptime > 3600:
			hours = int(uptime / 3600)
			uptime = round(uptime % 3600)
			return CommandResponseSuccess(f"Uptime: {hours} hours, {uptime} seconds")

		return CommandResponseSuccess(f"Uptime: {uptime} seconds")

	def cmd_cpu(self) -> CommandResponse:
		temp = None
		try:
			with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
				temp = float(f.read()) / 1000
		except FileNotFoundError:
			logging.error('Could not read CPU temperature')

		load = os.getloadavg()
		load = round(load[1])
		if temp is not None:
			return CommandResponseSuccess(f"CPU: {load}% load and {temp}°C")
		else:
			return CommandResponseSuccess(f"CPU: {load}% load")

	def cmd_temp(self) -> CommandResponse:
		temp = get_temperature()
		humidity = get_humidity()

		if temp is None:
			# Temperature not available.
			return CommandResponseError('Sorry, but no temperature is available right now.')
		elif humidity is None:
			# Temperature is, but humidity is not.
			fake_temp = round(temp * 1.8 + 32, 1)
			real_temp = round(temp, 1)
			return CommandResponseSuccess(f"Current temperature here is {real_temp}°C ({fake_temp}°F)")
		else:
			fake_temp = int(temp * 1.8 + 32)
			real_temp = int(temp)
			temps = f"{real_temp}°C ({fake_temp}°F)"
			pressure_change = get_pressure_change()

			if real_temp < 1:
				return CommandResponseSuccess(f"🥶 FREEZING! It's {temps} - Just stay home and get some hot chocolate!")

			if real_temp < 10:
				return CommandResponseSuccess(f"🧊 It's currently {temps} - Stay inside or bundle up!")

			if 10 <= real_temp < 18:
				if humidity > 80:
					return CommandResponseSuccess(f"☔ Damp and chilly, it's currently {temps}. Grab a waterproof coat.")

				if pressure_change == -1:
					return CommandResponseSuccess(f"☁️ A bit chilly at {temps} and rain may be on the horizon.")
				if pressure_change == 1:
					return CommandResponseSuccess(f"☀️ A bit chilly at {temps} but should be sunny.")
				return CommandResponseSuccess(f"A bit chilly right now at {temps}.")

			if 18 <= real_temp <= 24:
				if pressure_change == 0 or pressure_change == 1:
					if 30 <= humidity <= 60:
						return CommandResponseSuccess(f"☀️ Perfectly comfortable at {temps}.  Go out for a nice walk.")
					if humidity > 60:
						return CommandResponseSuccess(f"☁️ It's a comfortable {temps} but is rather sticky.")
				else:
					if 30 <= humidity <= 60:
						return CommandResponseSuccess(f"☁️ Perfectly comfortable at {temps} but it may storm soon.")
					if humidity > 60:
						return CommandResponseSuccess(f"☔ It's a comfortable {temps} but is rather wet out there.")

			if 24 < real_temp <= 29:
				hi = int(get_heat_index(real_temp, humidity))
				fake_hi = int(hi * 1.8 + 32)
				feels_like = f"{hi}°C ({fake_hi}°F)"

				if pressure_change == -1:
					return CommandResponseSuccess(f"☔ It's a hot and muggy {temps} and feels like {feels_like}.  Expect storms soon.")
				if hi > 32 and humidity > 70:
					return CommandResponseSuccess(f"🥵 It's a hot and muggy {temps} but feels like {feels_like}.  Take water & limit activity.")
				return CommandResponseSuccess(f"☀️ Warm and sunny at {temps}. Enjoy the heat!")

			if real_temp > 29:
				hi = int(get_heat_index(real_temp, humidity))
				fake_hi = int(hi * 1.8 + 32)
				if hi > 34 and humidity > 70:
					feels_like = f"{hi}°C ({fake_hi}°F"
					return CommandResponseSuccess(f"🔥 It's an oppressive {temps} & feels like {feels_like}. STAY SAFE AND HYDRATED!")

				if humidity <= 30:
					return CommandResponseSuccess(f"☀️ Hot and sunny at {temps} but very low humidity.  Enjoy the heat!")

				if pressure_change == -1:
					return CommandResponseSuccess(f"☀️ Hot and sunny at {temps} right now, but enjoy it while it lasts.  Storms may be on the horizon")

				return CommandResponseSuccess(f"☀️ Hot and sunny at {temps}. Enjoy the heat!")

			return CommandResponseSuccess(temps)

	def cmd_pressure(self) -> CommandResponse:
		pressure = get_pressure()
		pressure_change = get_pressure_change()

		if pressure is None:
			return CommandResponseError('Sorry, but no pressure is available right now.')

		pressure = round(pressure, 2)

		if pressure_change == 1:
			return CommandResponseSuccess(f"Pressure has rose to {pressure}hPa!  Expect sunny weather.")

		if pressure_change == -1:
			return CommandResponseSuccess(f"Pressure has fallen to {pressure}hPa!  Expect rainy weather.")

		return CommandResponseSuccess(f"Pressure is a stable {pressure}hPa")

	def cmd_daily_forecast(self) -> CommandResponse:
		"""
		Fetches the daily weather forecast and broadcasts it over the mesh network.
		"""

		if self.openweathermap_api_key is None or self.openweathermap_api_key == '':
			logging.error('No API key set for openweathermap.org, no forecast data available')
			return CommandResponseError('No API set for OpenWeatherMap.org, unable to fetch forecast data.')

		if self.location_lat is None or self.location_lat == '':
			logging.error('No latitude set, unable to pull forecast data.')
			return CommandResponseError('No latitude set, unable to pull forecast data.')

		if self.location_lon is None or self.location_lon == '':
			logging.error('No longitude set, unable to pull forecast data.')
			return CommandResponseError('No longitude set, unable to pull forecast data.')

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
				return CommandResponseError('Failed to retrieve forecast data.')

			low_f = round(forecast['low_temp'] * 1.8 + 32, 0)
			high_f = round(forecast['high_temp'] * 1.8 + 32, 0)

			# Format the message for broadcasting
			message = (
				f"{header}:\n{forecast['general_outlook']}\nLow/High: {forecast['low_temp']} / {forecast['high_temp']}°C\n({low_f} / {high_f}°F)"
			)
			return CommandResponseSuccess(message)
		except Exception as e:
			error_msg = f"Daily Weather: An error occurred during forecast fetching/broadcasting: {e}"
			print(f"Weather Forecast Error: {e}")
			return CommandResponseError(error_msg)

	def cmd_alerts(self) -> CommandResponse:
		if self.location_lat is None or self.location_lat == '':
			logging.error('No latitude set, unable to pull forecast data.')
			return CommandResponseError('No latitude set, unable to pull weather alerts.')

		if self.location_lon is None or self.location_lon == '':
			logging.error('No longitude set, unable to pull forecast data.')
			return CommandResponseError('No longitude set, unable to pull weather alerts.')

		if self.location_label is None or self.location_label == '':
			header = 'Weather Alerts'
		else:
			header = f'Alerts for {self.location_label}'

		logging.debug('--- Running Alerts Fetch ---')
		try:
			alerts = get_alerts(self.location_lat, self.location_lon)

			if len(alerts) == 0:
				return CommandResponseNoData('No weather alerts at this time.')

			return CommandResponseSuccess(f"{header}:\n" + '\n'.join(alerts))
		except Exception as e:
			error_msg = f"Weather Alerts: An error occurred during alert fetching/broadcasting: {e}"
			print(f"Weather Alerts Error: {e}")
			return CommandResponseError(error_msg)

	def cmd_reboot(self):
		"""
		Instruct the raspberry pi to reboot.
		"""
		with open('/tmp/reboot', 'w') as f:
			f.write('reboot')

		return CommandResponseSuccess('Reboot scheduled')

	def cmd_net(self):
		"""
		Get the net stats for the raspberry pi.
		:return:
		"""
		ip = get_local_ip()
		ssid = get_ssid()
		bars = get_bars()
		rate = get_rate()
		freq = get_frequency()
		return CommandResponseSuccess(f"IP: {ip}\nSSID: {ssid}\nBars: {bars}\nRate: {rate}\nFreq: {freq}")

	# --- Daily Forecast Integration ---
	async def run_daily_forecast(self) -> bool:
		"""Runs the forecast fetch and broadcasts it."""

		cmd = self.cmd_daily_forecast()

		if cmd.success and cmd.has_data:
			# Broadcast to all nodes (or a specific group if MESH_PORT is set)
			await self.radio.commands.send_chan_msg(self.weather_channel, cmd.message)
			return True
		else:
			return cmd.success

	async def run_alerts(self):
		cmd = self.cmd_alerts()

		if cmd.success and cmd.has_data:
			# Broadcast to all nodes (or a specific group if MESH_PORT is set)
			await self.radio.commands.send_chan_msg(self.weather_channel, cmd.message)
			return True
		else:
			return cmd.success

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
			cmd = None

			if ':' in text:
				text = text.split(':', 1)[1].strip().lower()

			if text == '!temp' or text == '!temperature':
				cmd = self.cmd_temp()
			elif text == '!humidity':
				humidity = get_humidity()
				if humidity is None:
					cmd = CommandResponseNoData('Sorry, but no humidity available')
				else:
					cmd = CommandResponseSuccess('Current humidity here is %s%%' % round(humidity, 1))
			elif text == '!pres' or text == '!pressure':
				cmd = self.cmd_pressure()
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
					cmd = CommandResponseSuccess('Current conditions here:\n' + ' | '.join(sensors))
				else:
					cmd = CommandResponseNoData('Sorry, but no sensor data is available')
			elif text == '!forecast':
				cmd = self.cmd_daily_forecast()
			elif text == '!alerts':
				cmd = self.cmd_alerts()

			if cmd is not None:
				await self.radio.commands.send_chan_msg(channel, cmd.message)

		else:
			logging.debug(f"Received message on channel {channel}: {text}")

	def run_event(self, event):
		from pprint import pprint
		pprint(event)

	def run_authorized_command(self, pubkey, cmd):
		authorized = pubkey != '' and pubkey in self.auth_radios
		if not authorized:
			return CommandResponseError(f"You are not authorized to use this command, add {pubkey} to authorize.")

		return cmd()

	async def run_direct_message(self, event):

		message = None
		text = event.payload.get('text', '').lower()
		target = event.payload.get('pubkey_prefix', '')

		from pprint import pprint
		pprint(event)

		if text == 'help':
			message = 'Available commands (* denotes auth req):\n'
			commands = [
				'ping', 'uptime', 'cpu', 'wake',
				'temp', 'pres', 'forecast', 'alerts',
				'reboot*', 'net*'
			]
			message += ' | '.join(commands)
		elif text == 'ping':
			message = self.cmd_ping().message
		elif text == 'uptime':
			message = self.cmd_uptime().message
		elif text == 'cpu':
			message = self.cmd_cpu().message
		elif text == 'temp' or text == 'temperature':
			message = self.cmd_temp().message
		elif text == 'pres' or text == 'pressure':
			message = self.cmd_pressure().message
		elif text == 'wake':
			# Write a file to wake the device up
			with open('/tmp/wake', 'w') as f:
				f.write('wake')
			message = 'Device display should wake up shortly.'
		elif text == 'forecast':
			message = self.cmd_daily_forecast().message
		elif text == 'alerts':
			message = self.cmd_alerts().message
		elif text == 'reboot':
			message = self.run_authorized_command(target, self.cmd_reboot).message
		elif text == 'net':
			message = self.run_authorized_command(target, self.cmd_net).message

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

		# Send notifications to admin devices to inform them the device has started (or restarted)
		for target in self.auth_radios:
			msg = 'Raspberry Pi Mesh Weather has started!'
			await self.radio.commands.send_msg(target, msg)

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

			if os.path.exists('/tmp/reboot'):
				logging.info('Rebooting...')
				os.system('sudo reboot')
				break

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
					successful = await self.run_daily_forecast()
					if successful:
						# Allow this to run multiple times if the first attempt failed.
						last_daily = now

				if now - last_alerts > ALERT_INTERVAL:
					successful = await self.run_alerts()
					if successful:
						# Allow this to run multiple times if the first attempt failed.
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
		print('ping: ' + watcher.cmd_ping().message)
		print('uptime: ' + watcher.cmd_uptime().message)
		print('cpu: ' + watcher.cmd_cpu().message)
		print('temp: ' + watcher.cmd_temp().message)
		print('pres: ' + watcher.cmd_pressure().message)
		print('forecast: ' + watcher.cmd_daily_forecast().message)
		print('alerts: ' + watcher.cmd_alerts().message)
		print('net: ' + watcher.cmd_net().message)
		sys.exit(0)

	asyncio.run(watcher.run())
