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

import json
import os


def store_contacts(contacts):
	"""
	Store discovered contacts in a temp file

	:param contacts:
	:return:
	"""
	HA_URL = os.getenv("HA_URL")

	with open('/tmp/mesh_contacts.json', 'w') as f:
		json.dump(contacts, f)


def get_contacts():
	if os.path.exists('/tmp/mesh_contacts.json'):
		with open('/tmp/mesh_contacts.json', 'r') as f:
			return json.load(f)
	else:
		return []


def get_repeater_names():
	contacts = get_contacts()
	repeaters = []
	for contact in contacts:
		if contact['type'] == 2:
			repeaters.append(contact['adv_name'])
	return repeaters
