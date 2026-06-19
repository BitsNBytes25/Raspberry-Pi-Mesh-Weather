import asyncio
import logging
import paho.mqtt.client as mqtt
import json

from raspberry_pi_mesh_weather.auth.mqtt_auth import MqttAuth
from raspberry_pi_mesh_weather.libs.config import MqttConfig, config


class MqttRunner:
	def __init__(self, options: MqttConfig):
		self.options = options
		self.client = None
		self.connected = False
		self.public_key: str | None = None
		self.auth: MqttAuth | None = None

	def set_auth(self, auth: MqttAuth | None):
		self.auth = auth

	def on_connect(self, client, userdata, flags, reason_code, properties):
		if reason_code == 0:
			logging.debug('MQTT Runner: Connected to %s', self.options.host)
			self.connected = True
		else:
			logging.warning('MQTT Runner: Failed to connect to %s: %s', self.options.host, reason_code)
			self.connected = False

	def on_publish(self, client, userdata, mid, reason_code, properties):
		if reason_code == mqtt.MQTT_ERR_SUCCESS:
			logging.debug('MQTT Runner: Publish successful (%s)', mid)
		else:
			logging.warning('MQTT Runner: Publish failed (%s): ', mid, reason_code)

	def resolve_topic(self, topic: str | None) -> str:
		"""
		Resolve a topic destination with common replacements

		:param topic:
		:return:
		"""
		if topic is None or topic == '':
			return ''
		else:
			return (
				topic.replace("{IATA}", config.location.iata.upper())
				.replace("{IATA_lower}", config.location.iata.lower())
				.replace("{PUBLIC_KEY}", self.public_key if self.public_key is not None else '')
			)

	async def start(self):
		logging.debug('MQTT Runner: Establishing connection to %s', self.options.host)
		logging.debug('MQTT Runner: Connection options: %s', self.options)

		if self.public_key is None:
			client_id = 'mesh-weather'
		elif self.options.client_prefix:
			client_id = '_'.join([self.options.client_prefix, self.public_key])
		else:
			client_id = self.public_key

		# Trim the client ID to the first 23 characters
		client_id = client_id[:23]

		self.client = mqtt.Client(
			callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
			client_id=client_id,
			reconnect_on_failure=True
		)
		self.client.on_connect = self.on_connect
		self.client.on_publish = self.on_publish

		# Paho supports automatic reconnection
		self.client.reconnect_delay_set(60, 300)

		if self.options.tls:
			logging.debug('MQTT Runner: Requiring TLS')
			self.client.tls_set()

			if not self.options.verify_tls:
				logging.debug('MQTT Runner: Skipping TLS verification (allow self signed certs)')
				self.client.tls_insecure_set(True)

		if self.auth is not None:
			logging.debug('MQTT Runner: Using authentication')
			credentials = await self.auth.get_credentials()
			self.client.username_pw_set(*credentials)
		else:
			logging.debug('MQTT Runner: Using no authentication')

		self.client.connect(self.options.host, self.options.port, keepalive=60)

		# Process callbacks in the background
		self.client.loop_start()

		# Give the connection a few seconds to connect.
		counter = 0
		while counter < 30 and not self.connected:
			counter += 1
			await asyncio.sleep(1)

	def push_data(self, topic: str, data: dict):
		"""
		Push data to an MQTT server under a given topic

		:param topic:
		:param data:
		:return:
		"""
		if not self.connected:
			# if the MQTT broker is not currently connected, don't push any data.
			return False

		# Allow the topic to be set from the config.
		if self.options.topic:
			topic = self.resolve_topic(self.options.topic)
		else:
			topic = self.resolve_topic(topic)

		logging.debug('MQTT Runner: Pushing payload to %s/%s: %s', self.options.host, topic, data)
		self.client.publish(topic, json.dumps(data), qos=1)

		# MQTT will not directly return a status on if the content was published,
		# as it is handled async on another thread.
		# At this stage however, it's been queued.
		return True
