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

import argparse
import logging
import time

from luma.core.interface.serial import spi
from luma.core.render import canvas
from luma.oled.device import sh1106
import os
from dotenv import load_dotenv
from .libs.get_local_ip import get_local_ip
from .libs.get_ssid import get_ssid
from .libs.humidity import get_humidity
from .libs.temperature import get_temperature
from .libs.pressure import get_pressure
from .libs.mesh_contacts import get_repeater_names


def main():
	parser = argparse.ArgumentParser(description="Meshcore Display Handler")

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

	# Set to False to disable the display support
	DISPLAY_ENABLED = os.getenv('DISPLAY_ENABLED', 'false').lower() == 'true'

	# Interface type of display, currently only "spi" is supported
	DISPLAY_TYPE = os.getenv('DISPLAY_TYPE', 'spi').lower()

	# SPI device ID, either 0 or 1
	DISPLAY_DEVICE = int(os.getenv('DISPLAY_DEVICE', 0))

	# SPI Port ID, probably 0
	DISPLAY_PORT = int(os.getenv('DISPLAY_PORT', 0))

	# Data Command GPIO ID
	DISPLAY_DC = int(os.getenv('DISPLAY_DC', 0))

	# Reset GPIO ID
	DISPLAY_RESET = int(os.getenv('DISPLAY_RESET', 0))

	# Connection baud rate
	DISPLAY_BAUD = int(os.getenv('DISPLAY_BAUD', 10000000))

	# Set to True to implement a short delay, required for some displays
	DISPLAY_RESET_DELAY = os.getenv('DISPLAY_RESET_DELAY', 'false').lower() == 'true'

	if not DISPLAY_ENABLED:
		print("Display support is disabled")
		return

	if DISPLAY_TYPE != 'spi':
		print("Display type not supported")
		return

	if DISPLAY_DEVICE not in [0, 1]:
		print("Display device not supported")
		return

	if DISPLAY_PORT not in [0, 1]:
		print("Display port not supported")
		return

	if DISPLAY_DC == 0:
		print('Display DC not configured!')
		return

	if DISPLAY_RESET == 0:
		print('Display RESET not configured!')
		return

	# Initialize SPI interface
	# port=0, device=0 corresponds to CE0 (Pin 24)
	# gpio_DC and gpio_RST match the pins in the table above
	try:
		serial = spi(
			device=DISPLAY_DEVICE,
			port=DISPLAY_PORT,
			gpio_DC=DISPLAY_DC,
			gpio_RST=DISPLAY_RESET,
			baudrate=DISPLAY_BAUD,
			reset_hold_time=0.2 if DISPLAY_RESET_DELAY else 0,
			reset_release_time=0.2 if DISPLAY_RESET_DELAY else 0
		)
	except Exception as e:
		print(f"Error: {e}")
		print('Connection to SPI device %s.%s failed' % (DISPLAY_DEVICE, DISPLAY_PORT))
		print('Did you forget to run "sudo raspi-config" and enable SPI?')
		return

	# 2. Initialize the SH1106 device
	device = sh1106(serial, rotate=2, width=128, height=64)

	# When the service starts (or restarts), the screen should be active by default.
	with open('/tmp/wake', 'w') as f:
		f.write('wake')

	counter = 0
	last_state = True
	while True:
		if not os.path.exists('/tmp/wake'):
			# Screen is off, sleep
			time.sleep(10)
			continue

		# If the wake file was last modified more than 120 seconds ago, sleep
		if os.path.exists('/tmp/wake') and (time.time() - os.path.getmtime('/tmp/wake')) > 120:
			logging.debug('Going back to sleep')
			os.remove('/tmp/wake')
			device.clear()
			last_state = False
			time.sleep(10)
			continue

		if not last_state:
			logging.debug('Waking up')
			last_state = True

		counter += 1
		if counter > 12:
			counter = 1

		# Which sensor value do we pull?
		if 1 <= counter < 5:
			temp = get_temperature()
			if temp is None:
				sensor = 'No Temperature Available'
			else:
				sensor = 'Temperature: %s°C' % round(temp, 1)
		elif 5 <= counter < 9:
			humidity = get_humidity()
			if humidity is None:
				sensor = 'No Humidity Available'
			else:
				sensor = 'Humidity: %s%%' % round(humidity, 1)
		else:
			pressure = get_pressure()
			if pressure is None:
				sensor = 'No Pressure Available'
			else:
				sensor = 'Pressure: %shPa' % round(pressure, 1)

		# Which network line do we pull?
		if 1 <= counter < 6:
			ip = get_local_ip()
			network = ip if ip else 'No IP Address'
		else:
			ssid = get_ssid()
			network = ssid if ssid else 'No SSID'

		# Which mesh data do we pull?
		repeaters = get_repeater_names()
		if len(repeaters) > 12:
			mesh = repeaters[counter - 1]
		else:
			window_size = 12 // len(repeaters)
			index = min(counter // window_size, len(repeaters) - 1)
			mesh = repeaters[index]

		with canvas(device) as draw:
			# draw.rectangle(device.bounding_box, outline="white")
			draw.text((10, 5), network, fill="white")
			draw.text((10, 25), sensor, fill="white")
			draw.text((10, 45), mesh, fill="white")

		time.sleep(1)
