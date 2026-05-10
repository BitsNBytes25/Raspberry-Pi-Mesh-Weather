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

import sys
import time
from dotenv import load_dotenv
import smbus2
import bme280
import os
from .libs.pressure import set_pressure
from .libs.temperature import set_temperature
from .libs.humidity import set_humidity
from .libs.home_assistant import push_to_ha
import argparse
import logging


def main():
	parser = argparse.ArgumentParser(description="Sensor Watcher Application")

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

	BME280_PORT = int(os.getenv('BME280_PORT', 1))
	BME280_ADDR = int(os.getenv('BME280_ADDR', 0x77), 16)
	addr_label = hex(BME280_ADDR)  # For pretty printing.
	HA_URL = os.getenv("HA_URL")
	HA_TOKEN = os.getenv("HA_TOKEN")
	ALTITUDE = float(os.getenv('ALTITUDE', 0))

	# Initialize I2C bus
	logging.debug(f"Connecting to BME280 on port {BME280_PORT}...")
	bus = smbus2.SMBus(BME280_PORT)

	# Load calibration parameters
	logging.debug(f"Loading calibration parameters on address {addr_label}...")
	calibration_params = bme280.load_calibration_params(bus, BME280_ADDR)

	# Wait a moment for calibration to complete
	logging.debug("Waiting 2 seconds for calibration to complete...")
	time.sleep(2)

	while True:
		try:
			# Read sensor data
			data = bme280.sample(bus, BME280_ADDR, calibration_params)

			logging.debug(f"Received data: {data}")
			p = data.pressure
			t = data.temperature
			h = data.humidity

			# Translate the pressure to Mean Sea Level Pressure (MSLP)
			if ALTITUDE > 0:
				# International Barometric Formula
				normalized_p = p / (1 - (ALTITUDE / 44330.0)) ** 5.255
				logging.debug(f"Normalized pressure {p} -> {normalized_p}")
				p = normalized_p

			# The BME280 has a crazy level of precision, but isn't overly accurate, so trim down the precision a bit
			p = round(p, 3)
			t = round(t, 2)
			h = round(h, 2)

			set_pressure(p)
			set_temperature(t)
			set_humidity(h)

			if HA_URL != '':
				# Push metrics to Home Assistant
				push_to_ha(HA_URL, HA_TOKEN, "temperature", t, "°C")
				push_to_ha(HA_URL, HA_TOKEN, "humidity", h, "%")
				push_to_ha(HA_URL, HA_TOKEN, "pressure", p, "hPa")

			time.sleep(60)
		except KeyboardInterrupt:
			logging.info("Keyboard interrupt received. Exiting...")
			sys.exit(0)
		except Exception as e:
			logging.error(f"An error occurred: {str(e)}")
			sys.exit(1)