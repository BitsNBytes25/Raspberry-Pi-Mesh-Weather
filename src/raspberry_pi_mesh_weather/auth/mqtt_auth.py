from raspberry_pi_mesh_weather.libs.config import MqttConfig


class MqttAuth():
	def __init__(self, options: MqttConfig):
		self.options = options

	def reauth_required(self) -> bool:
		"""
		Check if a re-auth is required.  Currently only supported for token-based authentication

		:return:
		"""
		return False

	async def get_credentials(self) -> tuple | None:
		"""
		Get the credentials for the requested MQTT server

		:return:
		"""
		return None
