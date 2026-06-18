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
import sys
import argparse
import logging

from raspberry_pi_mesh_weather.libs.commands import get_command
from raspberry_pi_mesh_weather.libs.config import config
from raspberry_pi_mesh_weather.services.displays.sh1106_display import Sh1106Display
from raspberry_pi_mesh_weather.services.misc.home_assistant import HomeAssistant
from raspberry_pi_mesh_weather.services.radios.meshcore_radio import MeshcoreRadio
from raspberry_pi_mesh_weather.services.sensors.bme280_sensor import Bme280Sensor


async def daemon_main(test: bool = False):
	"""
	Primary runner for the raspberry pi mesh helper application
	:return:
	"""

	# All the services that are running on this primary process
	services = []
	tasks = []

	# Load sensors
	for sensor_opts in config.sensors:
		if sensor_opts.type == 'bme280':
			sensor = Bme280Sensor(sensor_opts)
			logging.debug('Loading %s', sensor.get_name())
			loadable = await sensor.load()
			if loadable:
				if test:
					await sensor.test()
				else:
					services.append(sensor)
					tasks.append(sensor.start())
			else:
				logging.error('%s could not be loaded!', sensor.get_name())
		else:
			logging.error('Unsupported sensor type requested')

	# Load the appropriate radio
	if config.radio.type == 'meshcore':
		radio = MeshcoreRadio()
		logging.debug('Loading %s', radio.get_name())
		loadable = await radio.load()
		if loadable:
			if test:
				await radio.test()
			else:
				services.append(radio)
				tasks.append(radio.start())
		else:
			logging.error('%s could not be loaded!', radio.get_name())
	else:
		logging.error('Unsupported radio type requested')

	# Load Home Assistant integration if requested
	if config.home_assistant.url:
		ha = HomeAssistant()
		logging.debug('Loading %s', ha.get_name())
		loadable = await ha.load()
		if loadable:
			if test:
				await ha.test()
			else:
				services.append(ha)
				tasks.append(ha.start())
		else:
			logging.error('%s could not be loaded!', ha.get_name())

	# Load the display if one is enabled
	if config.display.enabled:
		if config.display.type == 'sh1106':
			display = Sh1106Display()
			logging.debug('Loading %s', display.get_name())
			loadable = await display.load()
			if loadable:
				if test:
					await display.test()
				else:
					services.append(display)
					tasks.append(display.start())
			else:
				logging.error('%s could not be loaded!', display.get_name())
		else:
			logging.warning('Unsupported display type requested')

	if test:
		# Get a list of commands to test too
		cmds = ['ping', 'uptime', 'cpu', 'temp', 'pres', 'humid', 'forecast', 'alerts', 'net']
		for cmd in cmds:
			c = get_command(cmd)
			if c is None:
				logging.warning('Command %s could not be loaded!', cmd)
			else:
				result = c('test')
				if result.success:
					logging.info('Command %s: %s', cmd, result.message)
				else:
					logging.warning('Command %s did not complete successfully', cmd)

		logging.debug('Test mode requested, exiting.')
		sys.exit(0)

	# Run all the services within this application
	try:
		await asyncio.gather(*tasks)
	except KeyboardInterrupt:
		logging.info('Keyboard interrupt received. Exiting...')
	except asyncio.CancelledError:
		logging.info('Shutdown signal received, exiting...')
	except Exception as e:
		logging.exception('Unexpected exception occurred', exc_info=e)
	finally:
		for service in services:
			await service.stop()
		sys.exit(0)


if __name__ == "__main__":
	parser = argparse.ArgumentParser(description="Meshcore Watcher Application")

	# Add the --debug flag
	# action="store_true" means it becomes True if present, and False if not
	parser.add_argument(
		'--debug',
		action='store_true',
		help='Enable debug mode with verbose logging'
	)

	parser.add_argument(
		'--test',
		action='store_true',
		help='Run all supported commands and exit without connecting to the mesh network'
	)

	args = parser.parse_args()

	if args.debug:
		logging.getLogger().setLevel(logging.DEBUG)
		logging.basicConfig(level=logging.DEBUG)
		logging.debug("Debug mode enabled")

	'''
	if args.test:
		print('ping: ' + watcher.cmd_ping().message)
		print('uptime: ' + watcher.cmd_uptime().message)
		print('cpu: ' + watcher.cmd_cpu().message)
		print('temp: ' + watcher.cmd_temp().message)
		print('pres: ' + watcher.cmd_pressure().message)
		print('forecast: ' + watcher.cmd_daily_forecast().message)
		print('alerts: ' + watcher.cmd_alerts().message)
		print('net: ' + watcher.cmd_net().message)
		sys.exit(0)
	'''
	asyncio.run(daemon_main(args.test))
