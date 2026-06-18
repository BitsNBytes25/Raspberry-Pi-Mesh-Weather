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
import logging
import time
from luma.core.interface.serial import spi
from luma.core.render import canvas
from luma.oled.device import sh1106

from raspberry_pi_mesh_weather.libs.system_state import state
from raspberry_pi_mesh_weather.services.service import Service
from raspberry_pi_mesh_weather.libs.get_local_ip import get_local_ip
from raspberry_pi_mesh_weather.libs.get_ssid import get_ssid
from raspberry_pi_mesh_weather.libs.humidity import get_humidity
from raspberry_pi_mesh_weather.libs.temperature import get_temperature
from raspberry_pi_mesh_weather.libs.pressure import get_pressure
from raspberry_pi_mesh_weather.libs.mesh_contacts import get_repeater_names
from raspberry_pi_mesh_weather.libs.config import config


class Sh1106Display(Service):
	def __init__(self):
		super().__init__()
		self.device = None

	async def load(self) -> bool:
		"""
		Load this service into core system memory and initialize all devices necessary

		If the service could not be loaded for whatever reason, False is returned.

		:return:
		"""

		if config.display.type != 'sh1106':
			logging.error('Invalid display type requested')
			return False

		if not config.display.enabled:
			logging.warning("Display support is disabled")
			return False

		if config.display.interface != 'spi':
			logging.error("Display type not supported")
			return False

		# Pull the defaults for this device
		rotate = 2 if config.display.rotate is None else config.display.rotate
		width = 128 if config.display.width is None else config.display.width
		height = 64 if config.display.height is None else config.display.height
		dev = 0 if config.display.device is None else config.display.device
		port = 0 if config.display.port is None else config.display.port
		dc_gpio = 25 if config.display.dc_gpio is None else config.display.dc_gpio
		reset_gpio = 24 if config.display.reset_gpio is None else config.display.reset_gpio
		baud_rate = 8000000 if config.display.baud_rate is None else config.display.baud_rate

		if dev not in [0, 1]:
			logging.error("Display device not supported")
			return False

		if port not in [0, 1]:
			logging.error("Display port not supported")
			return False

		# Initialize SPI interface
		# port=0, device=0 corresponds to CE0 (Pin 24)
		# gpio_DC and gpio_RST match the pins in the table above
		try:
			serial = spi(
				device=dev,
				port=port,
				gpio_DC=dc_gpio,
				gpio_RST=reset_gpio,
				baudrate=baud_rate,
				reset_hold_time=0.2 if config.display.reset_delay else 0,
				reset_release_time=0.2 if config.display.reset_delay else 0
			)
		except Exception as e:
			logging.error(f"Error: {e}")
			logging.error('Connection to SPI device %s.%s failed' % (dev, port))
			logging.error('Did you forget to run "sudo raspi-config" and enable SPI?')
			return False

		# 2. Initialize the SH1106 device
		self.device = sh1106(serial, rotate=rotate, width=width, height=height)

		# Set the default wake so it runs when this script first starts.
		state.set('wake', time.time())

		return True

	async def run(self):
		counter = 0
		last_state = True
		while self.running:
			if state.get('wake') + 120 < time.time():
				if last_state:
					logging.debug('Going back to sleep')
					self.device.clear()
					last_state = False

				# If the device has not been woken up recently, just do nothing.
				await asyncio.sleep(10)
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
			elif len(repeaters) > 0:
				window_size = 12 // len(repeaters)
				index = min(counter // window_size, len(repeaters) - 1)
				mesh = repeaters[index]
			else:
				mesh = 'No Repeaters'

			with canvas(self.device) as draw:
				# draw.rectangle(device.bounding_box, outline="white")
				draw.text((10, 5), network, fill="white")
				draw.text((10, 25), sensor, fill="white")
				draw.text((10, 45), mesh, fill="white")

			await asyncio.sleep(1)
