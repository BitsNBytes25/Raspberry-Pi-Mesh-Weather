import asyncio
import os
import time

from pprint import pprint
from dotenv import load_dotenv
from meshcore import MeshCore, EventType

from .libs.home_assistant import push_mesh_node_to_map
from .libs.humidity import get_humidity
from .libs.mesh_contacts import store_contacts
from .libs.pressure import get_pressure
from .libs.temperature import get_temperature

radio = None


async def handle_message(event):
	global radio

	channel = event.payload['channel_idx']
	text = event.payload.get('text', '')

	if channel == 1:
		# 1 is the weather channel, process it!
		sensor = None

		if ':' in text:
			text = text.split(':', 1)[1].strip().lower()

		if text == '!temp' or text == '!temperature':
			temp = get_temperature()
			if temp is None:
				sensor = 'Sorry, but no temperature is available right now.'
			else:
				sensor = 'Current temperature here is %s°C' % round(temp, 1)
		elif text == '!humidity':
			humidity = get_humidity()
			if humidity is None:
				sensor = 'Sorry, but no humidity available'
			else:
				sensor = 'Current humidity here is %s%%' % round(humidity, 1)
		elif text == '!pres' or text == '!pressure':
			pressure = get_pressure()
			if pressure is None:
				sensor = 'Sorry, but no pressure is available right now.'
			else:
				sensor = 'Current pressure here is %shPa' % round(pressure, 1)
		elif text == '!all':
			temp = get_temperature()
			humidity = get_humidity()
			pressure = get_pressure()
			sensors = []

			if temp is not None:
				sensors.append('Temperature: %s°C' % round(temp, 1))
			if humidity is not None:
				sensors.append('Humidity: %s%%' % round(humidity, 1))
			if pressure is not None:
				sensors.append('Pressure: %shPa' % round(pressure, 1))

			if len(sensors) > 0:
				sensor = 'Current conditions here: ' + ' | '.join(sensors)

		if sensor is not None:
			await radio.commands.send_chan_msg(channel, sensor)

	else:
		print(text)


def handle_event(event):
	pprint(event)


async def monitor_mesh(port, ha_url, ha_token):
	global radio
	radio = await MeshCore.create_serial(port, 115200)

	# Timers in seconds
	LOCAL_INTERVAL = 900  # 15 mins
	FLOOD_INTERVAL = 10800 # 3 hours

	last_local = 0
	last_flood = 0

	# Some devices allow setting this via custom variables or specific commands
	# This ensures discovered nodes are added to memory automatically
	await radio.commands.set_custom_var('auto_add_contacts', '1')

	await radio.ensure_contacts()

	print(f"Connected to {port}. Listening on #weather...")

	try:
		while True:
			now = time.time()

			# 1. Check for incoming events
			# radio.subscribe(None, handle_event)

			await radio.start_auto_message_fetching()

			await radio.commands.set_channel(1, '#weather')

			# radio.subscribe(EventType.CONTACT_MSG_RECV, handle_message)
			radio.subscribe(EventType.CHANNEL_MSG_RECV, handle_message)
			#event = await radio.wait_for_event(EventType.MSG_SENT, timeout=5)
			#if event:
			#	pprint(event)
			#	await handle_message(radio, event)

			# 2. Update Peer/Repeater list
			contacts = await radio.commands.get_contacts()
			if contacts.type != EventType.ERROR:
				# Store discovered contacts in a temp file so it can be used by other scripts.
				raw_contacts = list(contacts.payload.values())
				store_contacts(raw_contacts)

				if ha_url and ha_token != '':
					# Push these to Home Assistant too!
					for contact in raw_contacts:
						push_mesh_node_to_map(ha_url, ha_token, contact)

			# Send Zero-Hop (Local) Advert
			if now - last_local > LOCAL_INTERVAL:
				print("📡 Sending local advert...")
				await radio.commands.send_advert(False)
				last_local = now

			# Send Flood (Network-wide) Advert
			if now - last_flood > FLOOD_INTERVAL:
				print("🌊 Sending flood advert...")
				# Default hop limit (e.g., 3 or 4) tells the whole mesh who you are
				await radio.commands.send_advert(True)
				last_flood = now

			await asyncio.sleep(5)
	except KeyboardInterrupt:
		print("Exiting...")
		await radio.stop_auto_message_fetching()
		radio.stop()


def main():
	load_dotenv()

	MESH_PORT = os.getenv('MESH_PORT', '/dev/ttyUSB0')
	HA_URL = os.getenv("HA_URL")
	HA_TOKEN = os.getenv("HA_TOKEN")

	asyncio.run(monitor_mesh(MESH_PORT, HA_URL, HA_TOKEN))
