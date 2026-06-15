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
from datetime import datetime, timezone
from dotenv import load_dotenv
from meshcore import MeshCore, EventType

from .libs.home_assistant import push_mesh_node_to_map
from .libs.humidity import get_humidity
from .libs.mesh_contacts import store_contacts
from .libs.meshcore_packet import MeshcorePacket
from .libs.pressure import get_pressure, get_pressure_change
from .libs.temperature import get_temperature
from .libs.weather_forecast import WeatherForecast
from .libs.weather_alerts import get_alerts
from .libs.nmcli import get_bars, get_rate, get_ssid, get_frequency
from .libs.get_local_ip import get_local_ip
from .libs.config import config
from .libs.commands import get_command


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
		self.radio = None
		self.weather_channel = 1
		self.rf_data_cache = {}

	# --- Daily Forecast Integration ---
	async def run_daily_forecast(self) -> bool:
		"""Runs the forecast fetch and broadcasts it."""

		cmd = get_command('!forecast')
		if cmd is None:
			return False

		result = cmd(None)
		if result.success and result.has_data:
			# Broadcast to all nodes (or a specific group if MESH_PORT is set)
			await self.radio.commands.send_chan_msg(self.weather_channel, result.message)
			return True
		else:
			return result.success

	async def run_alerts(self) -> bool:
		cmd = get_command('!alerts')
		if cmd is None:
			return False

		result = cmd(None)
		if result.success and result.has_data:
			# Broadcast to all nodes (or a specific group if MESH_PORT is set)
			await self.radio.commands.send_chan_msg(self.weather_channel, result.message)
			return True
		else:
			return result.success

	async def run_channel_message(self, event):
		"""
		Handle messages received on a channel;
		these are generally public and replies are sent out to the entire channel
		:param event:
		:return:
		"""
		logging.debug('Parsing CHANNEL_MSG_RECV Event')

		channel = event.payload['channel_idx']
		text = event.payload.get('text', '')

		if channel == self.weather_channel:
			# 1 is the weather channel, process it!
			if ':' in text:
				text = text.split(':', 1)[1].strip().lower()
				cmd = get_command(text)

				if cmd is not None:
					result = cmd(None)
					await self.radio.commands.send_chan_msg(channel, result.message)

		else:
			logging.debug(f"Ignored message on channel {channel}: {text}")

	def run_event(self, event):
		from pprint import pprint
		pprint(event)

	async def run_direct_message(self, event):
		"""
		Event to handle direct messages received by this radio

		These are usually private queries for weather updates or other direct commands

		:param event:
		:return:
		"""
		logging.debug('Parsing CONTACT_MSG_RECV Event')

		text = event.payload.get('text', '').lower()
		target = event.payload.get('pubkey_prefix', '')

		cmd = get_command(text)
		if cmd is None:
			message = 'Sorry, I don\'t understand that command.  Try "help" for a list of commands.'
		else:
			message = cmd(target).message

		result = await self.radio.commands.send_msg(target, message)

		if result.type == EventType.ERROR:
			logging.error(f"Failed to send: {result.payload['reason']}")
		else:
			logging.debug(f"Reply sent to {target}")

	async def run_rx_log(self, event):
		logging.debug('Parsing RX_LOG_DATA Event: %s', event)
		from pprint import pprint
		import json
		packet = MeshcorePacket(event.payload)
		mqtt_payload = packet.as_mqtt()

		# Add the origin data based on the radio
		mqtt_payload['origin'] = self.radio.self_info['name']
		mqtt_payload['origin_id'] = self.radio.self_info['public_key']
		# print(json.dumps(event.payload))
		pprint(mqtt_payload)

		payload = event.payload

		if 'snr' not in payload:
			logging.error('RX_LOG_DATA Event has no snr')
			return

		# Try to get packet data - prefer 'payload' field, fallback to 'raw_hex'
		raw_hex = None

		# First, try the 'payload' field (already stripped of framing bytes)
		if 'payload' in payload and payload['payload']:
			raw_hex = payload['payload']
		# Fallback to raw_hex with first 2 bytes stripped
		elif 'raw_hex' in payload and payload['raw_hex']:
			raw_hex = payload['raw_hex'][4:]  # Skip first 2 bytes (4 hex chars)

		if raw_hex is None:
			logging.error('RX_LOG_DATA Event has no raw_hex')
			return

		packet_prefix = raw_hex[:32]

		rf_data = {
			'snr': payload.get('snr'),
			'rssi': payload.get('rssi'),
			'timestamp': time.time(),
			'raw_hex': raw_hex,
			'payload_length': payload.get('payload_length')
		}

		self.rf_data_cache[packet_prefix] = rf_data

		# Clean up old cache entries
		current_time = time.time()
		timeout = 10
		self.rf_data_cache = {
			k: v for k, v in self.rf_data_cache.items()
			if current_time - v['timestamp'] < timeout
		}

	async def run_raw_data(self, event):
		logging.debug('Parsing RAW_DATA Event')
		from pprint import pprint
		pprint(event.payload)

	async def run_status(self, event):
		logging.debug('Parsing STATUS_RESPONSE Event')
		from pprint import pprint
		pprint(event.payload)

	async def _setup_radio(self):
		radio_port = config.radio.port
		radio_baud = config.radio.baud_rate
		logging.debug(f"Connecting Meshcore via serial port {radio_port}")
		try:
			self.radio = await MeshCore.create_serial(radio_port, radio_baud)
		except FileNotFoundError:
			logging.error(f"Mesh radio not found on port {radio_port}.  Please check your settings.")
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
		self.rx_log_subscription = self.radio.subscribe(EventType.RX_LOG_DATA, self.run_rx_log)
		self.raw_data_subscription = self.radio.subscribe(EventType.RAW_DATA, self.run_raw_data)
		self.status_subscription = self.radio.subscribe(EventType.STATUS_RESPONSE, self.run_status)

		logging.debug('Mesh Radio Ready!')

		# Send notifications to admin devices to inform them the device has started (or restarted)
		for target in config.auth_radios:
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

					if config.home_assistant.url != '':
						# Push these to Home Assistant too!
						for contact in raw_contacts:
							push_mesh_node_to_map(contact)

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
				logging.info('Keyboard interrupt received. Exiting...')
				await self._shutdown_radio()
				sys.exit(0)
			except asyncio.CancelledError:
				logging.info('Shutdown signal received, exiting...')
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
