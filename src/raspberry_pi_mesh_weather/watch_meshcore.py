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

import asyncio
import os
import sys
import time
import argparse
import logging
from datetime import datetime
from dotenv import load_dotenv
from meshcore import MeshCore, EventType

from .libs.home_assistant import push_mesh_node_to_map
from .libs.humidity import get_humidity
from .libs.mesh_contacts import store_contacts
from .libs.pressure import get_pressure, get_pressure_change
from .libs.temperature import get_temperature
from .libs.weather_forecast import WeatherForecast

radio = None
MESH_PORT = None
HA_URL = None
HA_TOKEN = None
OPENWEATHERMAP_API_KEY = None
OPENWEATHERMAP_LOCATION = None
LOCATION_LABEL = None


def cmd_ping():
	return 'pong'


def cmd_uptime():
	with open('/proc/uptime', 'r') as f:
		uptime = float(f.read().split()[0])
		return f"Uptime: {uptime} seconds"


# --- Daily Forecast Integration (New Feature) ---
async def run_daily_forecast(channel):
	"""Runs the forecast fetch and broadcasts it."""
	global radio

	message = fetch_daily_forecast()
	if message == '':
		return

	if radio:
		# Broadcast to all nodes (or a specific group if MESH_PORT is set)
		await radio.commands.send_chan_msg(channel, message)
	else:
		print("Warning: Radio not initialized. Could not broadcast daily forecast.")
		print(f"Forecast message ready: {message}")


def fetch_daily_forecast() -> str:
	"""
	Fetches the daily weather forecast and broadcasts it over the mesh network.
	"""
	global OPENWEATHERMAP_API_KEY, OPENWEATHERMAP_LOCATION, LOCATION_LABEL

	if OPENWEATHERMAP_API_KEY is None or OPENWEATHERMAP_API_KEY == '':
		print('No API key set for openweathermap.org, no forecast data available')
		return ''

	if OPENWEATHERMAP_LOCATION is None or OPENWEATHERMAP_LOCATION == '':
		print('No location set for openweathermap.org, no forecast data available')
		return ''

	if LOCATION_LABEL is None or LOCATION_LABEL == '':
		header = 'Daily Forecast'
	else:
		header = f'Today for {LOCATION_LABEL}'

	print('--- Running Daily Weather Forecast Fetch ---')
	try:
		# Initialize the weather client (it will read OPENWEATHERMAP_API_KEY)
		weather_client = WeatherForecast(OPENWEATHERMAP_API_KEY)
		forecast = weather_client.get_daily_forecast(location=OPENWEATHERMAP_LOCATION)
		
		if not forecast:
			print('Weather Forecast: Failed to retrieve data.')
			return ''

		low_f = round(forecast['low_temp'] * 1.8 + 32, 0)
		high_f = round(forecast['high_temp'] * 1.8 + 32, 0)

		# Format the message for broadcasting
		message = (
			f"{header}:\n{forecast['general_outlook']}\nLow/High: {forecast['low_temp']} / {forecast['high_temp']}°C\n({low_f} / {high_f}°F)"
		)
		return message
	except Exception as e:
		error_msg = f"Daily Weather: An error occurred during forecast fetching/broadcasting: {e}"
		print(f"Weather Forecast Error: {e}")
		return error_msg


def cmd_cpu():
	temp = None
	with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
		temp = float(f.read()) / 1000

	load = os.getloadavg()
	load = load[1]
	if temp is not None:
		return f"CPU: {load}% load and {temp}°C"
	else:
		return f"CPU: {load}% load"


def get_heat_index(temp_c, humidity):
	# Heat Index is generally not applicable below 26.7C
	if temp_c < 26.7:
		return temp_c

	# Convert Celsius to Fahrenheit for the formula
	T = (temp_c * 9/5) + 32
	R = humidity

	# Constants for the Rothfusz regression
	hi_f = (-42.379 + (2.04901523 * T) + (10.14333127 * R) +
			(-0.22475541 * T * R) + (-0.00683783 * T**2) +
			(-0.05481717 * R**2) + (0.00122874 * T**2 * R) +
			(0.00085282 * T * R**2) + (-0.00000199 * T**2 * R**2))

	# Convert back to Celsius
	return (hi_f - 32) * 5/9


def cmd_temp():
	temp = get_temperature()
	humidity = get_humidity()

	if temp is None:
		# Temperature not available.
		return 'Sorry, but no temperature is available right now.'
	elif humidity is None:
		# Temperature is, but humidity is not.
		fake_temp = round(temp * 1.8 + 32, 1)
		real_temp = round(temp, 1)
		return f"Current temperature here is {real_temp}°C ({fake_temp}°F)"
	else:
		fake_temp = int(temp * 1.8 + 32)
		real_temp = int(temp)
		temps = f"{real_temp}°C ({fake_temp}°F)"
		pressure_change = get_pressure_change()

		if real_temp < 1:
			return f"🥶 FREEZING! It's {temps} - Just stay home and get some hot chocolate!"

		if real_temp < 10:
			return f"🧊 It's currently {temps} - Stay inside or bundle up!"

		if 10 <= real_temp < 18:
			if humidity > 80:
				return f"☔ Damp and chilly, it's currently {temps}. Grab a waterproof coat."

			if pressure_change == -1:
				return f"☁️ A bit chilly at {temps} and rain may be on the horizon."
			if pressure_change == 1:
				return f"☀️ A bit chilly at {temps} but should be sunny."
			return f"A bit chilly right now at {temps}."

		if 18 <= real_temp <= 24:
			if pressure_change == 0 or pressure_change == 1:
				if 30 <= humidity <= 60:
					return f"☀️ Perfectly comfortable at {temps}.  Go out for a nice walk."
				if humidity > 60:
					return f"☁️ It's a comfortable {temps} but is rather sticky."
			else:
				if 30 <= humidity <= 60:
					return f"☁️ Perfectly comfortable at {temps} but it may storm soon."
				if humidity > 60:
					return f"☔ It's a comfortable {temps} but is rather wet out there."

		if 24 < real_temp <= 29:
			hi = int(get_heat_index(real_temp, humidity))
			fake_hi = int(hi * 1.8 + 32)
			feels_like = f"{hi}°C ({fake_hi}°F)"

			if pressure_change == -1:
				return f"☔ It's a hot and muggy {temps} and feels like {feels_like}.  Expect storms soon."
			if hi > 32 and humidity > 70:
				return f"🥵 It's a hot and muggy {temps} but feels like {feels_like}.  Take water & limit activity."
			return f"☀️ Warm and sunny at {temps}. Enjoy the heat!"

		if real_temp > 29:
			hi = int(get_heat_index(real_temp, humidity))
			fake_hi = int(hi * 1.8 + 32)
			if hi > 34 and humidity > 70:
				feels_like = f"{hi}°C ({fake_hi}°F"
				return f"🔥 It's an oppressive {temps} & feels like {feels_like}. STAY SAFE AND HYDRATED!"

			if humidity <= 30:
				return f"☀️ Hot and sunny at {temps} but very low humidity.  Enjoy the heat!"

			if pressure_change == -1:
				return f"☀️ Hot and sunny at {temps} right now, but enjoy it while it lasts.  Storms may be on the horizon"

			return f"☀️ Hot and sunny at {temps}. Enjoy the heat!"

		return temps


def cmd_pressure():
	pressure = get_pressure()
	pressure_change = get_pressure_change()

	if pressure is None:
		return 'Sorry, but no pressure is available right now.'

	pressure = round(pressure, 2)

	if pressure_change == 1:
		return f"Pressure has rose to {pressure}hPa!  Expect sunny weather."

	if pressure_change == -1:
		return f"Pressure has fallen to {pressure}hPa!  Expect rainy weather."

	return f"Pressure is a stable {pressure}hPa"

async def handle_channel_message(event):
	"""
	Handle messages received on a channel;
	these are generally public and replies are sent out to the entire channel
	:param event:
	:return:
	"""
	global radio

	channel = event.payload['channel_idx']
	text = event.payload.get('text', '')

	from pprint import pprint
	pprint(event)

	if channel == 1:
		# 1 is the weather channel, process it!
		sensor = None

		if ':' in text:
			text = text.split(':', 1)[1].strip().lower()

		if text == '!temp' or text == '!temperature':
			sensor = cmd_temp()
		elif text == '!humidity':
			humidity = get_humidity()
			if humidity is None:
				sensor = 'Sorry, but no humidity available'
			else:
				sensor = 'Current humidity here is %s%%' % round(humidity, 1)
		elif text == '!pres' or text == '!pressure':
			sensor = cmd_pressure()
		elif text == '!all':
			temp = get_temperature()
			humidity = get_humidity()
			pressure = get_pressure()
			sensors = []

			if temp is not None:
				sensors.append('Temp: %s°C' % round(temp, 1))
			if humidity is not None:
				sensors.append('Humi: %s%%' % round(humidity, 1))
			if pressure is not None:
				sensors.append('Pres: %shPa' % round(pressure, 1))

			if len(sensors) > 0:
				sensor = 'Current conditions here:\n' + ' | '.join(sensors)
		elif text == '!forecast':
			sensor = fetch_daily_forecast()

		if sensor is not None:
			await radio.commands.send_chan_msg(channel, sensor)

	else:
		logging.debug(f"Received message on channel {channel}: {text}")


def handle_event(event):
	from pprint import pprint
	pprint(event)


async def handle_direct_message(event):
	global radio

	message = None
	text = event.payload.get('text', '').lower()
	target = event.payload.get('pubkey_prefix')

	if text == 'help':
		message = 'Available commands:\n'
		commands = ['ping', 'uptime', 'cpu', 'temp', 'pres', 'wake', 'forecast']
		message += ' | '.join(commands)
	elif text == 'ping':
		message = cmd_ping()
	elif text == 'uptime':
		message = cmd_uptime()
	elif text == 'cpu':
		message = cmd_cpu()
	elif text == 'temp' or text == 'temperature':
		message = cmd_temp()
	elif text == 'pres' or text == 'pressure':
		message = cmd_pressure()
	elif text == 'wake':
		# Write a file to wake the device up
		with open('/tmp/wake', 'w') as f:
			f.write('wake')
		message = 'Device display should wake up shortly.'
	elif text == 'forecast':
		message = fetch_daily_forecast()

	if message is None:
		message = 'Sorry, I don\'t understand that command.  Try "help" for a list of commands.'

	result = await radio.commands.send_msg(target, message)

	if result.type == EventType.ERROR:
		logging.error(f"Failed to send: {result.payload['reason']}")
	else:
		logging.debug(f"Reply sent to {target}")



async def monitor_mesh():
	global radio, MESH_PORT, HA_URL, HA_TOKEN

	logging.debug(f"Connecting Meshcore via serial port {MESH_PORT}")
	radio = await MeshCore.create_serial(MESH_PORT, 115200)

	# Timers in seconds
	LOCAL_INTERVAL = 900  # 15 mins
	FLOOD_INTERVAL = 10800 # 3 hours

	last_local = 0
	last_flood = 0
	last_daily = 0

	weather_channel = 1

	# Some devices allow setting this via custom variables or specific commands
	# This ensures discovered nodes are added to memory automatically
	logging.debug('Ensuring contacts are added automatically...')
	await radio.commands.set_custom_var('auto_add_contacts', '1')

	logging.debug('Ensuring contacts are added...')
	await radio.ensure_contacts()

	# Auto-fetch new messages
	logging.debug('Starting auto-message fetching...')
	await radio.start_auto_message_fetching()

	# Subscribe to the "#weather" channel
	logging.debug('Subscribing to channel #weather...')
	await radio.commands.set_channel(weather_channel, '#weather')

	# Checks ALL events
	# radio.subscribe(None, handle_event)

	# radio.subscribe(EventType.CONTACT_MSG_RECV, handle_message)

	logging.debug('Subscribing to channel messages...')
	channel_subscription = radio.subscribe(EventType.CHANNEL_MSG_RECV, handle_channel_message)
	direct_subscription = radio.subscribe(EventType.CONTACT_MSG_RECV, handle_direct_message)

	logging.debug('Mesh Radio Ready!')

	while True:
		try:
			now = time.time()
			hour = datetime.now().hour

			# 2. Update Peer/Repeater list
			contacts = await radio.commands.get_contacts()
			if contacts.type != EventType.ERROR:
				# Store discovered contacts in a temp file so it can be used by other scripts.
				raw_contacts = list(contacts.payload.values())
				store_contacts(raw_contacts)

				if HA_URL and HA_TOKEN != '':
					# Push these to Home Assistant too!
					for contact in raw_contacts:
						push_mesh_node_to_map(HA_URL, HA_TOKEN, contact)

			if now - last_flood > FLOOD_INTERVAL:
				# Send Flood (Network-wide) Advert
				logging.debug('Sending flood advert...')
				await radio.commands.send_advert(True)
				last_flood = now
				last_local = now
			elif now - last_local > LOCAL_INTERVAL:
				# Send Zero-Hop (Local) Advert
				logging.debug('Sending local advert...')
				await radio.commands.send_advert(False)
				last_local = now

			if 6 <= hour < 7 and now - last_daily > FLOOD_INTERVAL:
				# Sometime during the 6am hour, send the daily report.
				await run_daily_forecast(weather_channel)
				last_daily = now

			await asyncio.sleep(60)
		except KeyboardInterrupt:
			logging.info("Keyboard interrupt received. Exiting...")
			await radio.stop_auto_message_fetching()
			radio.unsubscribe(channel_subscription)
			radio.unsubscribe(direct_subscription)
			radio.stop()
			sys.exit(0)


def main():
	global MESH_PORT, HA_URL, HA_TOKEN, OPENWEATHERMAP_API_KEY, OPENWEATHERMAP_LOCATION, LOCATION_LABEL

	parser = argparse.ArgumentParser(description="Meshcore Watcher Application")

	# Add the --debug flag
	# action="store_true" means it becomes True if present, and False if not
	parser.add_argument(
		'--debug',
		action='store_true',
		help='Enable debug mode with verbose logging'
	)

	args = parser.parse_args()

	if args.debug:
		logging.getLogger().setLevel(logging.DEBUG)
		logging.basicConfig(level=logging.DEBUG)
		logging.debug("Debug mode enabled")

	load_dotenv()

	MESH_PORT = os.getenv('MESH_PORT', '/dev/ttyUSB0')
	HA_URL = os.getenv("HA_URL")
	HA_TOKEN = os.getenv("HA_TOKEN")
	OPENWEATHERMAP_API_KEY = os.getenv("OPENWEATHERMAP_API_KEY")
	OPENWEATHERMAP_LOCATION = os.getenv("OPENWEATHERMAP_LOCATION")
	LOCATION_LABEL = os.getenv("LOCATION_LABEL")

	asyncio.run(monitor_mesh())
