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

import time
import requests
from .config import config


def push_to_ha(sensor_name, value, unit):
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


def push_mesh_node_to_map(info):
	ha_url = config.home_assistant.url
	ha_token = config.home_assistant.token

	HEADERS = {
		"Authorization": f"Bearer {ha_token}",
		"content-type": "application/json",
	}
	# Create a slug-friendly ID from the pubkey (e.g., sensor.mesh_node_a1b2c3d4)
	pubkey = info.get("public_key", "")
	entity_id = f"device_tracker.mesh_node_{pubkey[:8].lower()}"
	url = f"{ha_url}/api/states/{entity_id}"

	lat = info.get("adv_lat")
	lng = info.get("adv_lon")

	# Only push if coordinates exist
	if lat and lng:
		payload = {
			"state": "home" if info.get("lastmod", 0) > (time.time() - 3600) else "not_home",
			"attributes": {
				"latitude": float(lat),
				"longitude": float(lng),
				"source_type": "gps",
				"friendly_name": info.get("adv_name", f"Mesh {pubkey[:8]}"),
				"icon": "mdi:antenna"
			}
		}

		try:
			requests.post(url, headers=HEADERS, json=payload, timeout=5)
		except Exception as e:
			print(f"Map Push Error: {e}")
