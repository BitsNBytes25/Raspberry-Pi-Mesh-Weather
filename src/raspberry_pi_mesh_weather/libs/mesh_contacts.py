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
