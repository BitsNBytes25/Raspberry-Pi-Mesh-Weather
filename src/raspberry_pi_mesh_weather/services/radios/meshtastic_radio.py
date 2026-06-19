import asyncio
from datetime import datetime
import logging
import time

import meshtastic
import meshtastic.serial_interface
from google.protobuf.json_format import MessageToDict
from meshtastic.serial_interface import SerialInterface
from pubsub import pub

from raspberry_pi_mesh_weather.auth.mqtt_auth_simple import MqttAuthSimple
from raspberry_pi_mesh_weather.libs.commands import get_command
from raspberry_pi_mesh_weather.libs.config import config
from raspberry_pi_mesh_weather.libs.mesh_contacts import MeshContact, store_contact
from raspberry_pi_mesh_weather.libs.mqtt import MqttRunner
from raspberry_pi_mesh_weather.services.service import Service


class MeshtasticRadio(Service):
	def __init__(self):
		super().__init__()
		self.radio: SerialInterface | None = None
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
			self.radio.sendText(text=result.message)
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
			self.radio.sendText(text=result.message)
			return True
		else:
			return result.success

	def run_direct_message(self, packet, interface):
		"""
		Event to handle direct messages received by this radio

		These are usually private queries for weather updates or other direct commands

		:param event:
		:return:
		"""
		logging.error('Parsing CONTACT_MSG_RECV Event: %s', packet)

		# Extract destination routing addresses
		destination = packet.get("to")
		sender_raw = packet.get("from")

		radio_id = interface.localNode.nodeNum
		direct = destination == radio_id

		# Format the sender's ID into standard !hex format for replying
		if isinstance(sender_raw, int):
			target = f"!{sender_raw:08x}"
		else:
			target = str(sender_raw)

		text = packet.get("decoded", {}).get("text", "").lower()

		cmd = get_command(text)
		if cmd is None:
			if direct:
				message = 'Sorry, I don\'t understand that command.  Try "help" for a list of commands.'
			else:
				# Just ignore them
				message = ''
		else:
			message = cmd(target).message

		if direct:
			interface.sendText(text=message, destinationId=target)
			logging.debug(f"Reply sent to {target}")
		elif message:
			interface.sendText(text=message)
			logging.debug(f"Sent response to general")

	def run_rx_log(self, packet, interface):
		if not packet:
			return

		if not interface:
			return

		def safe_serialize_val(val):
			"""Recursively converts bytes to hexadecimal strings for JSON compliance."""
			if hasattr(val, "DESCRIPTOR"):
				return MessageToDict(val, preserving_proto_field_name=True)
			if isinstance(val, bytes):
				return val.hex()  # Converts b'\x12\x34' to "1234"
			if isinstance(val, dict):
				return {k: safe_serialize_val(v) for k, v in val.items()}
			if isinstance(val, list):
				return [safe_serialize_val(item) for item in val]
			return val

		logging.debug('Parsing RX_LOG_DATA Packet: %s', packet)

		if config.location.region is not None:
			# Allow the region to be defined manually
			region = config.location.region
		else:
			# automatic from the radio
			region = interface.localNode.localConfig.lora.region
			if region == 1:
				region = 'US'
			elif region == 2 or region == 3 or 29 <= region <= 32:
				region = 'EU'
			elif region == 4:
				region = 'CN'
			elif region == 5:
				region = 'JP'
			elif region == 6 or region == 22:
				region = 'ANZ'
			elif region == 7:
				region = 'KR'
			elif region == 8:
				region = 'TW'
			elif region == 9:
				region = 'RU'
			elif region == 10:
				region = 'IN'
			elif region == 11:
				region = 'NZ'
			elif region == 12:
				region = 'TH'
			elif region == 14 or region == 15:
				region = 'UA'
			elif region == 16 or region == 17:
				region = 'MY'
			elif region == 18:
				region = 'SG'
			elif region == 19 or region == 20 or region == 21:
				region = 'PH'
			elif region == 23 or region == 24:
				region = 'KZ'
			elif region == 25:
				region = 'NP'
			elif region == 26:
				region = 'BR'
			else:
				region = 'UNSET'

		channel_name = interface.localNode.channels[0].settings.name
		channel_id = packet.get("channel", 0)

		# Extract the source hardware node identifier
		# Meshtastic nodes use integers natively, convert to standard !hex format
		raw_sender = packet.get("from") or packet.get("fromId")
		if isinstance(raw_sender, int):
			node_hex = f"!{raw_sender:08x}"
		else:
			node_hex = str(raw_sender) if raw_sender else "!unknown"

		# Build policy-compliant topic string
		topic = '/'.join([
			'msh',
			region,
			str(channel_id),
			'json',
			channel_name,
			node_hex
		])

		payload = {
			"channel": channel_id,
			"from": packet.get("from"),
			"to": packet.get("to"),
			"id": packet.get("id"),
			"type": "packet",
			"timestamp": int(time.time())
		}

		# Inject safely decoded data if available
		if "decoded" in packet:
			payload["payload"] = safe_serialize_val(packet["decoded"])

		if self.mqtt_connections is not None:
			for connection in self.mqtt_connections:
				connection.push_data(topic, payload)

	async def _setup_mqtt(self):
		self.mqtt_connections = []
		for opts in config.mqtt:
			# Each mqtt is a set of options for a different broker,
			# This allows the user to define multiple targets to publish data to.
			if opts.usage == 'packets':
				# only register MQTT servers that are for packet captures
				runner = MqttRunner(opts)

				if opts.username:
					auth = MqttAuthSimple(opts)
				else:
					auth = None

				runner.set_auth(auth)
				await runner.start()
				self.mqtt_connections.append(runner)

	async def _setup_radio(self):
		"""
		Set up and connect to the meshcore radio
		:return:
		"""
		radio_port = config.radio.port
		logging.debug(f"Connecting Meshtastic via serial port {radio_port}")
		try:
			self.radio = meshtastic.serial_interface.SerialInterface(devPath=radio_port)
		except FileNotFoundError:
			logging.error(f"Mesh radio not found on port {radio_port}.  Please check your settings.")
			return

		if not self.radio:
			logging.error('Could not connect to Mesh Radio')
			return

	async def stop(self):
		if self.radio is None:
			return

		pub.unsubAll()

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
		# @todo
		pass

	async def run(self):
		# Timers in seconds
		FLOOD_INTERVAL = 3600  # 1 hour
		ALERT_INTERVAL = 1800  # 30 minutes

		last_flood = 0
		last_daily = 0
		last_alerts = 0

		logging.debug('Subscribing to channel messages...')
		pub.subscribe(self.run_rx_log, 'meshtastic.receive')
		pub.subscribe(self.run_direct_message, 'meshtastic.receive.text')

		logging.debug('Mesh Radio Ready!')

		while self.running:
			now = time.time()
			hour = datetime.now().hour

			# Update Peer/Repeater list
			contacts = self.radio.nodes
			raw_contacts = list(contacts.values())
			logging.debug('contacts: %s', raw_contacts)
			for contact in raw_contacts:
				# Convert this to a standardized Contact (so it works on both MT and MC)
				# and save to the persistent state
				store_contact(MeshContact.from_meshmastic(contact))

			if now - last_flood > FLOOD_INTERVAL:
				# Send Flood (Network-wide) Advert
				logging.debug('Sending flood advert...')
				self.radio.sendTelemetry()
				last_flood = now

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
