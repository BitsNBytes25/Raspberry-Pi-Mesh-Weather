import asyncio
import logging
import smbus2
import bme280

from raspberry_pi_mesh_weather.libs.config import SensorConfig, config
from raspberry_pi_mesh_weather.libs.humidity import set_humidity
from raspberry_pi_mesh_weather.libs.pressure import set_pressure
from raspberry_pi_mesh_weather.libs.temperature import set_temperature
from raspberry_pi_mesh_weather.services.service import Service


class Bme280Sensor(Service):
	def __init__(self, options: SensorConfig):
		super().__init__()
		self.options = options
		self.bus = None
		self.calibration_params = None

	async def load(self) -> bool:
		if self.options.type != 'bme280':
			logging.error('Sensor type for BME280 does not match configuration.')
			return False

		addr_label = hex(self.options.address)  # For pretty printing.

		# Initialize I2C bus
		logging.debug(f"Connecting to BME280 on port {self.options.port}...")
		self.bus = smbus2.SMBus(self.options.port)

		# Load calibration parameters
		logging.debug(f"Loading calibration parameters on address {addr_label}...")
		self.calibration_params = bme280.load_calibration_params(self.bus, self.options.address)

		# Wait a moment for calibration to complete
		logging.debug("Waiting 2 seconds for calibration to complete...")
		await asyncio.sleep(2)

		# Perform an initial read to confirm sensor is connected
		data = bme280.sample(self.bus, self.options.address, self.calibration_params)

		return True

	async def test(self):
		"""
		Perform a manual test of this sensor
		:return:
		"""
		data = bme280.sample(self.bus, self.options.address, self.calibration_params)

		logging.info('BME280: temperature: %s', data.temperature)
		logging.info('BME280: pressure: %s', data.pressure)
		logging.info('BME280: humidity: %s', data.humidity)

		if config.location.altitude > 0:
			logging.info('BME280: Using altitude of %s to normalize pressure', config.location.altitude)
			# International Barometric Formula
			normalized_p = data.pressure / (1 - (config.location.altitude / 44330.0)) ** 5.255
			logging.info('BME280: normalized pressure: %s', normalized_p)
		else:
			logging.info('BME280: No altitude set, no correction for barometric pressure')

	async def run(self):
		while self.running:
			# Read sensor data
			data = bme280.sample(self.bus, self.options.address, self.calibration_params)

			logging.debug('BME280: Received data: %s', data)
			p = data.pressure
			t = data.temperature
			h = data.humidity

			# Translate the pressure to Mean Sea Level Pressure (MSLP)
			if config.location.altitude > 0:
				# International Barometric Formula
				normalized_p = p / (1 - (config.location.altitude / 44330.0)) ** 5.255
				logging.debug(f"Normalized pressure {p} -> {normalized_p}")
				p = normalized_p

			# The BME280 has a crazy level of precision, but isn't overly accurate, so trim down the precision a bit
			p = round(p, 3)
			t = round(t, 2)
			h = round(h, 2)

			set_pressure(p)
			set_temperature(t)
			set_humidity(h)

			await asyncio.sleep(10)
