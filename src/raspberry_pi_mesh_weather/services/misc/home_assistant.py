import asyncio
import time
import requests

from raspberry_pi_mesh_weather.libs.config import config
from raspberry_pi_mesh_weather.libs.humidity import get_humidity
from raspberry_pi_mesh_weather.libs.mesh_contacts import MeshContact, get_contacts, MeshContactType
from raspberry_pi_mesh_weather.libs.pressure import get_pressure
from raspberry_pi_mesh_weather.libs.temperature import get_temperature
from raspberry_pi_mesh_weather.services.service import Service


class HomeAssistant(Service):
	def __init__(self):
		super().__init__()

	async def load(self) -> bool:
		ha_url = config.home_assistant.url
		ha_token = config.home_assistant.token

		if ha_url is None or ha_url == '':
			return False

		if ha_token is None or ha_token == '':
			return False

		try:
			response = requests.get(ha_url, timeout=5)
			response.raise_for_status()
			return True
		except Exception as e:
			print(f"Home Assistant Error ({ha_url}): {e}")
			return False

	async def run(self):
		while self.running:
			temp = get_temperature()
			if temp is not None:
				self.push_to_ha('temperature', temp, 'C')

			pressure = get_pressure()
			if pressure is not None:
				self.push_to_ha('pressure', pressure, 'hPa')

			humidity = get_humidity()
			if humidity is not None:
				self.push_to_ha('humidity', humidity, '%')

			contacts = get_contacts()
			for contact in contacts:
				if contact.lat and contact.lon and contact.last_heard + 300 >= time.time():
					self.push_mesh_node_to_map(contact)

			await asyncio.sleep(60)

	def push_to_ha(self, sensor_name, value, unit):
		ha_url = config.home_assistant.url
		ha_token = config.home_assistant.token

		HEADERS = {
			"Authorization": f"Bearer {ha_token}",
			"content-type": "application/json",
		}
		url = f"{ha_url}/api/states/sensor.mesh_{sensor_name}"
		payload = {
			"state": value,
			"attributes": {
				"unit_of_measurement": unit,
				"friendly_name": f"Mesh {sensor_name.capitalize()}"
			}
		}
		try:
			response = requests.post(url, headers=HEADERS, json=payload, timeout=5)
			response.raise_for_status()
		except Exception as e:
			print(f"HA Push Error ({sensor_name}): {e}")


	def push_mesh_node_to_map(self, contact: MeshContact):
		ha_url = config.home_assistant.url
		ha_token = config.home_assistant.token

		HEADERS = {
			"Authorization": f"Bearer {ha_token}",
			"content-type": "application/json",
		}
		# Create a slug-friendly ID from the pubkey (e.g., sensor.mesh_node_a1b2c3d4)
		pubkey = contact.public_key
		short_pubkey = pubkey[:8].lower()
		entity_id = f"device_tracker.mesh_node_{short_pubkey}"
		url = f"{ha_url}/api/states/{entity_id}"

		lat = contact.lat
		lng = contact.lon

		# Allow the operator to set a custom icon based on the device ID
		# Defaults to automatic detection based off the type.
		icon = None
		if config.home_assistant.icons is not None:
			if short_pubkey in config.home_assistant.icons:
				icon = config.home_assistant.icons[short_pubkey]

		if icon is None:
			if short_pubkey.upper() in config.auth_radios or short_pubkey in config.auth_radios:
				icon = 'mdi:human-greeting-proximity'
			elif contact.type == MeshContactType.REPEATER:
				icon = 'mdi:access-point'
			elif contact.type == MeshContactType.CLIENT:
				icon = 'mdi:smart-card'
			elif contact.type == MeshContactType.SENSOR:
				icon = 'mdi:chip'
			elif contact.type == MeshContactType.ROOM:
				icon = 'mdi:server'
			else:
				icon = 'mdi:antenna'

		payload = {
			#"state": "home" if info.get("lastmod", 0) > (time.time() - 3600) else "not_home",
			'state': 'home',
			"attributes": {
				"latitude": float(lat),
				"longitude": float(lng),
				"source_type": "gps",
				"friendly_name": contact.name,
				"icon": icon
			}
		}

		try:
			requests.post(url, headers=HEADERS, json=payload, timeout=5)
		except Exception as e:
			print(f"Map Push Error: {e}")
