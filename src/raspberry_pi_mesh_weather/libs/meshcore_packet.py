import hashlib
import logging
from datetime import datetime, timezone
from meshcore.meshcore_parser import MeshcorePacketParser


class MeshcorePacket:
	"""
	Extract metadata from a given raw payload of a Meshcore packet,
	as provided by the `RX_LOG_DATA` event.

	@see https://github.com/meshcore-dev/MeshCore/blob/main/docs/packet_format.md
	"""
	def __init__(self, payload: dict | None):


		### Initialize all variables for this object

		self.header = 0
		"""
		Header byte from the packet, contains the version, payload type, and route type
		
		:param int:
		"""

		self.route_type = 0
		"""
		Route type
		
		- 0 = Flood Routing w/ transport codes
		- 1 = Flood Routing
		- 2 = Direct Routing
		- 3 = Direct Routing w/ transport codes
		 
		:param int:
		"""

		self.payload_type = 0
		"""
		Payload type
		
		- 0 = Request (destination/source hashes + MAC)
		- 1 = Response to REQ or ANON_REQ
		- 2 = Plain text message
		- 3 = Acknowledgement
		- 4 = Node advertisement
		- 5 = Group text
		- 6 = Group datagram
		- 7 = Anonymous request
		- 8 = Returned path
		- 9 = Trace a path (collecting SNR for each hop)
		- 10 = Multipart sequence of packets
		- 11 = Control packet data
		- 12 = reserved
		- 13 = reserved
		- 14 = reserved
		- 15 = Custom packet (raw bytes, custom encryption)
		
		:param int:
		"""

		self.payload_version = 0
		"""
		Payload version
		
		- 0 = v1 - 1-byte src/dest hashes, 2-byte MAC
		- 1 = v2 - future
		- 2 = v3 - future
		- 3 = v4 - future
		
		:param int:
		"""

		self.path_hash_size = 0
		"""
		Number of bytes per hop to store
		
		:param int:
		"""

		self.path = []
		"""
		List of router idents this packet has travelled through
		
		:param list<str>:
		"""

		self.raw = b''
		"""
		Raw packet data, complete with headers
		
		:param bytes:
		"""

		self.payload = b''
		"""
		Payload contents data, just the user data
		
		:param bytes:
		"""

		self.hash = ''
		"""
		@todo figure out what hash means
		
		:param str:
		"""

		self.time = None
		"""
		Datetime this packet was received
		
		:param datetime:
		"""

		self.snr = 0.0
		"""
		Signal-to-noise ratio of this received packet, as recorded by the radio
		
		:param float:
		"""

		self.rssi = 0.0
		"""
		Received Signal Strength Indicator
		
		The power level of the received signal as recorded by the radio
		
		Right next to the radio would be 0 to -30 dBm
		Strong signal would be -30 to -60 dBm
		Weak signal would be -60 to -90 dBm
		
		:param float:
		"""

		self.type = None
		"""
		The node type, if this packet is an advertisement
		
		- 0 = No type set
		- 1 = Chat (companion radio)
		- 2 = Repeater
		- 3 = Room server
		- 4 = Sensor
		
		:param int | None:
		"""

		self.name = None
		"""
		The node name, if this packet is an advertisement
		
		:param str | None:
		"""

		self.lat = None
		"""
		The node latitude, if this packet is an advertisement
		
		:param float | None:
		"""

		self.lon = None
		"""
		The node longitude, if this packet is an advertisement
		
		:param float | None:
		"""

		### Populate simple values from the radio
		if payload is not None:
			self.load_payload(payload)

	def load_payload(self, payload):

		if 'recv_time' in payload:
			self.time = datetime.fromtimestamp(payload['recv_time'])
		else:
			self.time = datetime.now(timezone.utc)

		if 'payload' in payload and payload['payload']:
			# First, try the 'payload' field (already stripped of framing bytes)
			self.raw = bytes.fromhex(payload['payload'])
		elif 'raw_hex' in payload and payload['raw_hex']:
			# Fallback to raw_hex with first 2 bytes stripped
			self.raw = bytes.fromhex(payload['raw_hex'][4:])  
		else:
			logging.error('MeshcorePacket: payload data has no raw_hex nor payload')
			return

		# Extract RF data if available, these are not included in the packet but are provided by the local radio
		if 'snr' in payload:
			self.snr = float(payload['snr'])
		if 'rssi' in payload:
			self.rssi = float(payload['rssi'])

		if 'path_hash_size' in payload and 'path' in payload and 'path_len' in payload:
			offset = 0
			path_size = payload['path_hash_size'] * 2
			for i in range(payload['path_len']):
				self.path.append(payload['path'][offset:offset + path_size])
				offset += path_size

		if 'header' in payload:
			self.header = payload['header']
		if 'route_type' in payload:
			self.route_type = payload['route_type']
		if 'payload_type' in payload:
			self.payload_type = payload['payload_type']
		if 'payload_ver' in payload:
			self.payload_version = payload['payload_ver']
		if 'path_hash_size' in payload:
			self.path_hash_size = payload['path_hash_size']
		if 'pkt_payload' in payload:
			self.payload = payload['pkt_payload']
		if 'pkt_hash' in payload:
			self.hash = payload['pkt_hash']

		# Adverts may have additional details
		if 'adv_type' in payload:
			self.type = payload['adv_type']
		if 'adv_name' in payload:
			self.name = payload['adv_name']
		if 'adv_lat' in payload:
			self.lat = payload['adv_lat']
		if 'adv_lon' in payload:
			self.lon = payload['adv_lon']

		if self.raw and self.payload == b'':
			# User payload was not set, extract it out of the raw payload.
			# This generally doesn't happen in production, but is useful in testing from JSON files.
			self._parse_payload()

	def _parse_payload(self):
		"""
		Manually parse out the payload from the raw bytes.

		Needs to skip the headers to jump straight to the user content.
		:return:
		"""

		# Skip the header (1 byte), path (1 byte), and transport codes if set (0 or 4 bytes)
		offset = 6 if self.route_type == 0 or self.route_type == 3 else 2

		# Jump past the routing table (variable byte length)
		offset += len(self.path) * self.path_hash_size

		self.payload = self.raw[offset:]

	async def parse(self, raw_data: bytes):
		"""
		Parse the raw packet payload to extract the useful data; uses the MeshcorePacketParser interally
		:return:
		"""
		parser = MeshcorePacketParser()
		data = await parser.parsePacketPayload(raw_data)

		self.load_payload(data)

	def as_mqtt(self) -> dict:
		"""
		Get this packet as a valid MQTT packet which can be sent on that network

		:return:
		"""

		if self.route_type == 0 or self.route_type == 1:
			route = 'F'  # Used for both TRANSPORT_FLOOD and FLOOD
		elif self.route_type == 2:
			route = 'D'
		elif self.route_type == 3:
			route = 'T'
		else:
			route = 'U'

		packet_data = {
			"timestamp": self.time.isoformat(),
			"type": "PACKET",
			"direction": "rx",
			"time": self.time.strftime("%H:%M:%S"),
			"date": self.time.strftime("%d/%m/%Y"),
			"len": str(len(self.raw)),
			"packet_type": str(self.payload_type),
			"route": route,
			"payload_len": str(len(self.payload)),
			"raw": self.raw.hex().upper(),
			"SNR": str(self.snr),
			"RSSI": str(self.rssi),
			"hash": self.get_packet_hash()
		}

		# Add path for route=D like mctomqtt.py
		if route == 'D' and len(self.path):
			packet_data['path'] = ','.join(self.path)

		return packet_data

	def get_packet_hash(self) -> str:
		"""Calculate hash for packet identification - based on packet.cpp"""
		try:
			# Calculate hash exactly like MeshCore Packet::calculatePacketHash():
			# 1. Payload type (1 byte)
			# 2. Path length (2 bytes as uint16_t, little-endian) - ONLY for TRACE packets (type 9)
			# 3. Payload data
			hash_obj = hashlib.sha256()
			hash_obj.update(bytes([self.payload_type]))

			if self.payload_type == 9:  # PAYLOAD_TYPE_TRACE
				# C++ does: sha.update(&path_len, sizeof(path_len))
				# path_len is uint16_t, so sizeof(path_len) = 2 bytes
				# Convert wire path_len byte to 2-byte little-endian uint16_t
				hash_obj.update(len(self.path).to_bytes(2, byteorder='little'))

			hash_obj.update(self.payload)

			# Return first 16 hex characters (8 bytes) in uppercase
			return hash_obj.hexdigest()[:16].upper()
		except Exception as e:
			logging.debug(f"Error calculating hash: {e}")
			return "0000000000000000"
