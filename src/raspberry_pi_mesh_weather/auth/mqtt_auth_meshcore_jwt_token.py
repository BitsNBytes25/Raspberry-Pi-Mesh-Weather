import json
import time
import jwt
import jwt.utils
from meshcore import MeshCore

from raspberry_pi_mesh_weather.auth.mqtt_auth import MqttAuth
from raspberry_pi_mesh_weather.libs.config import MqttConfig


class MqttAuthMeshcoreJwtToken(MqttAuth):
	def __init__(self, options: MqttConfig, radio: MeshCore):
		super().__init__(options)
		self.radio = radio
		self.expires = 0

	def reauth_required(self) -> bool:
		"""
		Check if a re-auth is required.  Currently only supported for token-based authentication

		:return:
		"""

		# Default expiration time; take the timeout sans a bit of buffer
		exp_time = self.get_token_expiration() - 60
		if exp_time <= 0:
			return False

		return self.options.token and 0 < self.token_expiry < exp_time

	def get_token_expiration(self) -> int:
		"""
		Get the expiration timestamp of a token based on configurable parameters.

		:return:
		"""

		timeout = self.options.token_timeout
		if timeout is None:
			# Default
			timeout = 3600

		if timeout == 0:
			# No timeout necessary
			return 0

		return int(time.time()) + timeout

	async def get_credentials(self) -> tuple:
		# Generate a JWT token for authentication
		self.expires = self.get_token_expiration()
		pub_key = self.radio.self_info['public_key']
		header = {"alg": "EdDSA", "typ": "JWT"}
		now = int(time.time())
		payload = {
			'iss': 'Raspberry Pi Mesh Weather',  # Issuer
			'iat': now,  # Issued At Time
			'exp': self.expires,  # Expiration time (60 minutes)
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
		username = f"v1_{pub_key}"
		return username, password