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

from enum import Enum

from raspberry_pi_mesh_weather.libs.system_state import state


class MeshContactType(Enum):
	UNKNOWN = 0
	"""
	Unknown / other type of contact
	"""

	CLIENT = 1
	"""
	MT: CLIENT, CLIENT_MUTE, CLIENT_HIDDEN, TAK
	MC: CHAT
	"""

	REPEATER = 2
	"""
	MT: CLIENT_BASE, REPEATER, ROUTER, ROUTER_LATE
	MC: REPEATER
	"""

	ROOM = 3
	"""
	MT: N/A
	MC: ROOM
	"""

	SENSOR = 4
	"""
	MT: TRACKER, LOST_AND_FOUND, SENSOR, TAK_TRACKER
	MC: SENSOR
	"""


class MeshContact:
	def __init__(self):
		self.public_key: str | None = None
		self.name: str | None = None
		self.lat: float | None = None
		self.lon: float | None = None
		self.last_heard: int = 0
		self.type: MeshContactType = MeshContactType.UNKNOWN

	@classmethod
	def from_meshmastic(cls, raw):
		c = MeshContact()
		c.public_key = raw['user']['id'][1:]
		c.name = raw['user']['longName']

		if 'position' in raw:
			if 'latitude' in raw['position']:
				c.lat = raw['position']['latitude']
			if 'longitude' in raw['position']:
				c.lon = raw['position']['longitude']

		role = raw['user']['role'] if 'role' in raw['user'] else None
		if role is None:
			# Probably the user's radio
			c.type = MeshContactType.CLIENT
		elif role in ['CLIENT', 'CLIENT_MUTE', 'CLIENT_HIDDEN', 'TAK']:
			c.type = MeshContactType.CLIENT
		elif role in ['CLIENT_BASE', 'REPEATER', 'ROUTER', 'ROUTER_LATE']:
			c.type = MeshContactType.REPEATER
		elif role in ['TRACKER', 'LOST_AND_FOUND', 'SENSOR', 'TAK_TRACKER']:
			c.type = MeshContactType.SENSOR

		if 'lastHeard' in raw:
			c.last_heard = raw['lastHeard']

		return c

	@classmethod
	def from_meshcore(cls, raw):
		c = MeshContact()
		c.public_key = raw['public_key']

		if 'adv_name' in raw:
			c.name = raw['adv_name']
		if 'adv_lat' in raw:
			c.lat = raw['adv_lat']
		if 'adv_lon' in raw:
			c.lon = raw['adv_lon']
		if 'type' in raw:
			if raw['type'] == 1:
				c.type = MeshContactType.CLIENT
			elif raw['type'] == 2:
				c.type = MeshContactType.REPEATER
			elif raw['type'] == 3:
				c.type = MeshContactType.ROOM
			elif raw['type'] == 4:
				c.type = MeshContactType.SENSOR

		if 'last_advert' in raw and 'lastmod' in raw:
			c.last_heard = int(max(raw['last_advert'], raw['lastmod']))

		return c


def store_contact(contact: MeshContact):
	"""
	Store a discovered contact in the application state

	:param contact:
	:return:
	"""

	contacts = state.get('contacts', [])
	exists = False
	for saved_contact in contacts:
		if saved_contact.public_key == contact.public_key:
			# Merge this contact (vs outright replacing)
			exists = True
			if contact.last_heard is not None:
				saved_contact.last_heard = max(saved_contact.last_heard, contact.last_heard)
			if contact.lat is not None:
				saved_contact.lat = contact.lat
			if contact.lon is not None:
				saved_contact.lon = contact.lon
			break
	if not exists:
		contacts.append(contact)

	state.set('contacts', contacts)


def get_contacts() -> list[MeshContact]:
	return state.get('contacts', [])


def get_repeater_names() -> list[str]:
	contacts = get_contacts()
	repeaters = []
	for contact in contacts:
		if contact.type == MeshContactType.REPEATER:
			repeaters.append(contact.name)
	return repeaters
