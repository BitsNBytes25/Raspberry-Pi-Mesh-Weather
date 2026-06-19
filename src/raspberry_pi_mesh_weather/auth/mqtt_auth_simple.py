from raspberry_pi_mesh_weather.auth.mqtt_auth import MqttAuth
from raspberry_pi_mesh_weather.libs.config import MqttConfig


class MqttAuthSimple(MqttAuth):
	"""
	Simple username/password authentication for MQTT

	"""
	def __init__(self, options: MqttConfig):
		super().__init__(options)

	async def get_credentials(self) -> tuple | None:
		return self.options.username, self.options.password