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

import psutil

from raspberry_pi_mesh_weather.libs.commands import get_command
from raspberry_pi_mesh_weather.libs.config import config, SensorConfig
from raspberry_pi_mesh_weather.services.service import ShutdownRequested, Service


async def _load_radio(radio_name: str = '') -> tuple[Service|None, bool]:
	"""
	Lazy load the requested radio service

	Handles failures like import failed.
	:param radio_name:
	:return:
	"""

	try:
		if radio_name == 'meshcore':
			from raspberry_pi_mesh_weather.services.radios.meshcore_radio import MeshcoreRadio
			radio = MeshcoreRadio()
		elif radio_name == 'meshtastic':
			from raspberry_pi_mesh_weather.services.radios.meshtastic_radio import MeshtasticRadio
			radio = MeshtasticRadio()
		elif radio_name == 'cli':
			from raspberry_pi_mesh_weather.services.radios.cli_radio import CliRadio
			radio = CliRadio()
		else:
			logging.error('Unsupported radio type requested')
			return None, False
	except Exception as e:
		logging.error('%s could not be loaded: %s', radio_name, e)
		return None, False

	logging.info('Loading radio %s', radio.get_name())
	loadable = await radio.load()

	if not loadable:
		logging.error('%s could not be loaded!', radio.get_name())
	return radio, loadable


async def _load_sensor(sensor_opts: SensorConfig) -> tuple[Service|None, bool]:
	"""
	Lazy load a sensor

	:param sensor_opts:
	:return:
	"""
	try:
		if sensor_opts.type == 'bme280':
			from raspberry_pi_mesh_weather.services.sensors.bme280_sensor import Bme280Sensor
			sensor = Bme280Sensor(sensor_opts)
		else:
			logging.error('Unsupported sensor type requested: [%s]', sensor_opts.type)
			return None, False
	except Exception as e:
		logging.error('%s could not be loaded: %s', sensor_opts.type, e)
		return None, False

	logging.info('Loading sensor %s', sensor.get_name())
	loadable = await sensor.load()
	if not loadable:
		logging.error('%s could not be loaded!', sensor.get_name())
	return sensor, loadable


async def _load_resolver(service_name: str, *args, **kwargs) -> tuple[Service | None, bool]:
	"""
	Load the AI command resolver, trying the candidate backends in priority
	order until one loads.

	:return: (service, loadable) — the loaded resolver service and True, or
		(None, False) when AI is disabled or no backend could load.
	"""
	try:
		mem_threshold = 1980 * 1024 * 1024
		mem_avail = psutil.virtual_memory().total

		if service_name == 'ai':
			from raspberry_pi_mesh_weather.services.ai import AiService
			service = AiService()
		elif service_name == 'auto' and mem_avail >= mem_threshold:
			from raspberry_pi_mesh_weather.services.ai import AiService
			service = AiService()
		elif service_name == 'nltk':
			from raspberry_pi_mesh_weather.services.nltk import NltkService
			service = NltkService()
		elif service_name == 'auto' and mem_avail < mem_threshold:
			from raspberry_pi_mesh_weather.services.nltk import NltkService
			service = NltkService()
		else:
			logging.error('Unsupported command resolver type requested: [%s]', service_name)
			return None, False
	except Exception as e:
		logging.error('Command resolver %s could not be loaded: %s', service_name, e)
		return None, False

	logging.info('Loading resolver %s', service.get_name())
	loadable = await service.load()
	if not loadable:
		logging.error('%s could not be loaded!', service.get_name())
	return service, loadable


async def _load_service(service_name: str, *args, **kwargs) -> tuple[Service|None, bool]:
	"""
	Lazy load a generic service

	:param service_name:
	:param args: positional constructor arguments
	:param kwargs: keyword constructor arguments
	:return:
	"""
	try:
		if service_name == 'tasks':
			from raspberry_pi_mesh_weather.services.scheduled_tasks import ScheduledTasks
			service = ScheduledTasks(*args, **kwargs)
		elif service_name == 'homeassistant':
			from raspberry_pi_mesh_weather.services.misc.home_assistant import HomeAssistant
			service = HomeAssistant()
		elif service_name == 'sh1106_display':
			from raspberry_pi_mesh_weather.services.displays.sh1106_display import Sh1106Display
			service = Sh1106Display()
		else:
			logging.error('Unsupported service requested: [%s]', service_name)
			return None, False
	except Exception as e:
		logging.error('%s could not be loaded: %s', service_name, e)
		return None, False

	logging.info('Loading service %s', service.get_name())
	loadable = await service.load()
	if not loadable:
		logging.error('%s could not be loaded!', service.get_name())
	return service, loadable


async def daemon_main(test: bool = False):
	"""
	Primary runner for the raspberry pi mesh helper application
	:return:
	"""

	# All the services that are running on this primary process
	services = []

	# Load sensors
	for sensor_opts in config.sensors:
		sensor, loadable = await _load_sensor(sensor_opts)
		if loadable and sensor:
			services.append(sensor)

	# Load the appropriate radio
	radio, radio_loaded = await _load_radio(config.radio.type)
	if radio_loaded and radio:
		services.append(radio)

	# Load the AI command resolver if requested (opt-in): the sentence
	# transformer resolver on capable hardware, with the lightweight nltk
	# resolver as fallback when it cannot load (see `_load_ai_service`)
	if config.resolver.enabled:
		resolver, loadable = await _load_resolver(config.resolver.backend)
		if loadable and resolver:
			services.append(resolver)
		else:
			logging.error('Command resolver could not be loaded')

	# Load the shared scheduled tasks service (currently runs the morning and
	# evening forecast broadcast, which is radio-independent once the radio
	# implements `broadcast`)
	if radio_loaded and radio:
		scheduled, loadable = await _load_service('tasks', radio)
		if loadable and scheduled:
			services.append(scheduled)

	# Load Home Assistant integration if requested
	if config.home_assistant.url:
		ha, loadable = await _load_service('homeassistant')
		if loadable and ha:
			services.append(ha)

	# Load the display if one is enabled
	if config.display.enabled:
		if config.display.type == 'sh1106':
			display, loadable = await _load_service('sh1106_display')
			if loadable and display:
				services.append(display)
		else:
			logging.warning('Unsupported display type requested')

	if test:
		logging.info('TEST mode requested; running quick service tests and exiting!')

		for service in services:
			await service.test()
		# Get a list of commands to test too
		from .libs.commands.handler import _direct_commands
		cmds = []
		for cmd in _direct_commands.keys():
			if not _direct_commands[cmd]._settings['auth']:
				cmds.append(cmd)
		for cmd in cmds:
			print('')
			c = get_command(cmd)
			if c is None:
				print('Command %s - success: False, error: Could not be loaded!' % cmd)
			else:
				result = c('test')
				if result.success and result.message:
					print('Command %s - success: True, response:\n%s' % (cmd, result.message))
				elif result.success:
					print('Command %s - success: True, response: no response provided' % cmd)
				else:
					print('Command %s - success: False, error: Did not complete successfully' % cmd)

		logging.debug('Test mode requested, exiting.')
		sys.exit(0)

	tasks = []
	for service in services:
		tasks.append(service.start())

	# Run all the services within this application
	process = psutil.Process()
	mem_used = round(process.memory_info().rss / 1024 / 1024, 0)
	logging.info('Daemon ready, using %dMB memory', mem_used)
	try:
		await asyncio.gather(*tasks)
	except KeyboardInterrupt:
		logging.info('Keyboard interrupt received. Exiting...')
	except ShutdownRequested:
		logging.info('Shutdown requested. Exiting...')
	except asyncio.CancelledError:
		logging.info('Shutdown signal received, exiting...')
	except Exception as e:
		logging.exception('Unexpected exception occurred', exc_info=e)
	finally:
		for service in services:
			await service.stop()
		sys.exit(0)


def main():
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
	else:
		logging.basicConfig(level=logging.INFO)

	asyncio.run(daemon_main(args.test))

if __name__ == "__main__":
	main()
