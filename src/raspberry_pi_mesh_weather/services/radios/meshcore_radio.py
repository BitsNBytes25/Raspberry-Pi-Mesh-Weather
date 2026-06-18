import asyncio
from datetime import datetime
import logging
import time

from meshcore import MeshCore, EventType

from raspberry_pi_mesh_weather.libs.commands import get_command
from raspberry_pi_mesh_weather.libs.config import config
from raspberry_pi_mesh_weather.libs.mesh_contacts import MeshContact, store_contact
from raspberry_pi_mesh_weather.libs.meshcore_packet import MeshcorePacket
from raspberry_pi_mesh_weather.libs.mqtt import MqttRunner
from raspberry_pi_mesh_weather.services.service import Service


class MeshcoreRadio(Service):
	def __init__(self):
		super().__init__()
		self.status_subscription = None
		self.raw_data_subscription = None
		self.rx_log_subscription = None
		self.direct_subscription = None
		self.channel_subscription = None
		self.radio = None
		self.weather_channel = 1
		self.mqtt_connections = None

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
		packet = MeshcorePacket(event.payload)

		if self.mqtt_connections is not None:
			for connection in self.mqtt_connections:
				connection.push_packet_event(packet)

	async def run_raw_data(self, event):
		logging.debug('Parsing RAW_DATA Event')
		from pprint import pprint
		pprint(event.payload)

	async def run_status(self, event):
		logging.debug('Parsing STATUS_RESPONSE Event')
		from pprint import pprint
		pprint(event.payload)

	async def _setup_mqtt(self):
		self.mqtt_connections = []
		for opts in config.mqtt:
			# Each mqtt is a set of options for a different broker,
			# This allows the user to define multiple targets to publish data to.
			runner = MqttRunner(self.radio, opts)
			await runner.start()
			self.mqtt_connections.append(runner)

	async def _setup_radio(self):
		"""
		Set up and connect to the meshcore radio
		:return:
		"""
		radio_port = config.radio.port
		radio_baud = config.radio.baud_rate
		logging.debug(f"Connecting Meshcore via serial port {radio_port}")
		try:
			self.radio = await MeshCore.create_serial(radio_port, radio_baud)
		except FileNotFoundError:
			logging.error(f"Mesh radio not found on port {radio_port}.  Please check your settings.")
			return

		if not self.radio:
			logging.error('Could not connect to Mesh Radio')
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

		# Sync the clock
		await self.radio.commands.set_time(int(time.time()))

	async def stop(self):
		if self.radio is None:
			return

		await self.radio.stop_auto_message_fetching()
		self.radio.unsubscribe(self.channel_subscription)
		self.radio.unsubscribe(self.direct_subscription)
		self.radio.unsubscribe(self.rx_log_subscription)
		self.radio.unsubscribe(self.raw_data_subscription)
		self.radio.unsubscribe(self.status_subscription)
		self.radio.stop()

		self.radio = None
		self.running = False

	async def load(self) -> bool:
		# Set up the radio connection
		await self._setup_radio()

		# Try to set up MQTT brokers that are requested,
		# This must be done after a connection to the radio is established.
		await self._setup_mqtt()

		return True

	async def test(self):
		contacts = await self.radio.commands.get_contacts()
		if contacts.type != EventType.ERROR:
			raw_contacts = list(contacts.payload.values())
			for contact in raw_contacts:
				# Convert this to a standardized Contact (so it works on both MT and MC)
				# and save to the persistent state
				c = MeshContact.from_meshcore(contact)
				logging.info('MeshCore: Visible Contact: %s - %s', c.public_key[:8], c.name)

		dev_bat = await self.radio.commands.get_bat()
		dev_time = await self.radio.commands.get_time()
		dev_tel = await self.radio.commands.get_self_telemetry()
		dev_tuning = await self.radio.commands.get_tuning()
		logging.info('MeshCore: Battery: %s', dev_bat)
		logging.info('MeshCore: Time: %s', dev_time)
		logging.info('MeshCore: Telemetry: %s', dev_tel)
		logging.info('MeshCore: Tuning: %s', dev_tuning)

	async def run(self):
		# Timers in seconds
		LOCAL_INTERVAL = 900  # 15 minutes
		FLOOD_INTERVAL = 10800  # 3 hours
		ALERT_INTERVAL = 1800  # 30 minutes

		last_local = 0
		last_flood = 0
		last_daily = 0
		last_alerts = 0

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

		while self.running:
			now = time.time()
			hour = datetime.now().hour

			# Update Peer/Repeater list
			contacts = await self.radio.commands.get_contacts()
			if contacts.type != EventType.ERROR:
				raw_contacts = list(contacts.payload.values())
				logging.debug('contacts: %s', raw_contacts)
				for contact in raw_contacts:
					# Convert this to a standardized Contact (so it works on both MT and MC)
					# and save to the persistent state
					store_contact(MeshContact.from_meshcore(contact))

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
