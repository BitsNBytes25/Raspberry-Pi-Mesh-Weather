import asyncio
import logging
import time

import paho.mqtt.client as mqtt
import jwt
import json
from jwt.utils import base64url_decode
from meshcore import MeshCore

from raspberry_pi_mesh_weather.libs.config import MqttConfig, config
from raspberry_pi_mesh_weather.libs.meshcore_packet import MeshcorePacket


class MqttRunner:
	def __init__(self, radio: MeshCore, options: MqttConfig):
		self.radio = radio
		self.options = options
		self.public_key = self.radio.self_info['public_key'].upper()
		self.client = mqtt.Client(
			callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
			client_id=self.public_key,
			reconnect_on_failure=True
		)
		self.client.on_connect = self.on_connect
		self.client.on_publish = self.on_publish
		self.token_expiry = 0
		self.connected = False
		self.topic = (
			options.topic.replace("{IATA}", config.location.iata.upper())
				.replace("{IATA_lower}", config.location.iata.lower())
				.replace("{PUBLIC_KEY}", self.public_key)
		)
		if options.client_prefix:
			self.client_id = '_'.join([options.client_prefix, self.public_key])
		else:
			self.client_id = self.public_key

		# Trim the client ID to the first 23 characters
		self.client_id = self.client_id[:23]

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

	async def start(self):
		logging.debug('MQTT Runner: Establishing connection to %s', self.options.host)
		logging.debug('MQTT Runner: Connection options: %s', self.options)
		# Paho supports automatic reconnection
		self.client.reconnect_delay_set(60, 300)

		if self.options.tls:
			logging.debug('MQTT Runner: Requiring TLS')
			self.client.tls_set()

			if not self.options.verify_tls:
				logging.debug('MQTT Runner: Skipping TLS verification (allow self signed certs)')
				self.client.tls_insecure_set(True)

		if self.options.token:
			# Generate a JWT token for authentication
			logging.debug('MQTT Runner: Using token authentication')
			pub_key = self.radio.self_info['public_key']
			header = {"alg": "EdDSA", "typ": "JWT"}
			now = int(time.time())
			payload = {
				'iss': 'Raspberry Pi Mesh Weather',  # Issuer
				'iat': now,  # Issued At Time
				'exp': now + 3600,  # Expiration time (60 minutes)
				'public_key': pub_key
			}
			if self.options.token_audience is not None:
				# Include the token audience if requested.
				payload['aud'] = self.options.token_audience

			# Serialize and Base64URL encode the JSON structural chunks
			header_json = json.dumps(header, separators=(',', ':')).encode('utf-8')
			payload_json = json.dumps(payload, separators=(',', ':')).encode('utf-8')

			header_b64 = jwt.utils.base64url_encode(header_json)
			payload_b64 = jwt.utils.base64url_encode(payload_json)

			# The string that must be signed in a JWT is always: 'encodedHeader.encodedPayload'
			signing_input = f"{header_b64}.{payload_b64}".encode('utf-8')

			# Stream the data to the MeshCore hardware crypto engine
			await self.radio.commands.sign_start()
			await self.radio.commands.sign_data(signing_input)
			raw_sig = await self.radio.commands.sign_finish()

			# Convert raw signature bytes to Base64URL
			signature_b64 = jwt.utils.base64url_encode(raw_sig)

			password = f"{header_b64}.{payload_b64}.{signature_b64}"

			self.client.username_pw_set(f"v1_{pub_key}", password)
		elif self.options.username and self.options.password:
			# Simple username/password authentication
			logging.debug('MQTT Runner: Using user/pass authentication')
			self.client.username_pw_set(self.options.username, self.options.password)
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

	def push_packet_event(self, packet: MeshcorePacket):
		"""
		Push a packet to the MQTT server, usually for tracking all traffic.

		:return:
		"""

		if not self.connected:
			# if the MQTT broker is not currently connected, don't push any data.
			return False

		if packet.route_type == 0 or packet.route_type == 1:
			route = 'F'  # Used for both TRANSPORT_FLOOD and FLOOD
		elif packet.route_type == 2:
			route = 'D'
		elif packet.route_type == 3:
			route = 'T'
		else:
			route = 'U'

		packet_data = {
			'origin': self.radio.self_info['name'],
			'origin_id': self.radio.self_info['public_key'].upper(),
			"timestamp": packet.time.isoformat(),
			"type": "PACKET",
			"direction": "rx",
			"time": packet.time.strftime("%H:%M:%S"),
			"date": packet.time.strftime("%d/%m/%Y"),
			"len": str(len(packet.raw)),
			"packet_type": str(packet.payload_type),
			"route": route,
			"payload_len": str(len(packet.payload)),
			"raw": packet.raw.hex().upper(),
			"SNR": str(packet.snr),
			"RSSI": str(packet.rssi),
			"hash": packet.get_packet_hash()
		}

		# Add path for route=D like mctomqtt.py
		if route == 'D' and len(packet.path):
			packet_data['path'] = ','.join(packet.path)

		logging.debug('MQTT Runner: Pushing packet to %s/%s: %s', self.options.host, self.topic, packet_data)
		self.client.publish(self.topic, json.dumps(packet_data), qos=1)

		# MQTT will not directly return a status on if the content was published,
		# as it is handled async on another thread.
		# At this stage however, it's been queued.
		return True
