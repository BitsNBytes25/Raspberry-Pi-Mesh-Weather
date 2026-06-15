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

import os
import logging
import functools
from typing import Callable

from .humidity import get_humidity
from .pressure import get_pressure, get_pressure_change
from .temperature import get_temperature
from .weather_forecast import WeatherForecast
from .weather_alerts import get_alerts
from .nmcli import get_bars, get_rate, get_ssid, get_frequency
from .get_local_ip import get_local_ip
from .config import config


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

_group_commands = {}
_direct_commands = {}

def command(
	name: str,
	auth: bool = False,
	direct: bool = False,
	group: bool = False
):
	def decorator(func):
		# Attach the metadata to the function object
		func._settings = {
			'auth': auth
		}

		if direct:
			_direct_commands[name] = func

		if group:
			_group_commands[name] = func

		@functools.wraps(func)
		def wrapper(pubkey: str | None = None, *args, **kwargs):
			authorized = pubkey is not None and pubkey != '' and pubkey in config.auth_radios
			if auth and not authorized:
				return CommandResponseError(f"You are not authorized to use this command, add {pubkey} to authorize.")
			else:
				return func(*args, **kwargs)
		return wrapper
	return decorator


class CommandResponse:
	"""
	Simple wrapper for command responses,
	useful to know between "" means an error or
	"" means just no data but successful.
	"""
	def __init__(self, success=True, has_data=True, message=None):
		self.success = success
		self.has_data = has_data
		self.message = message


class CommandResponseError(CommandResponse):
	def __init__(self, message=None):
		CommandResponse.__init__(self, False, False, message)


class CommandResponseSuccess(CommandResponse):
	def __init__(self, message=None):
		CommandResponse.__init__(self, True, True, message)


class CommandResponseNoData(CommandResponse):
	def __init__(self, message=None):
		CommandResponse.__init__(self, True, False, message)


def get_command(cmd: str) -> Callable[[str | None], CommandResponse] | None:
	"""
	Get the underlying command based on the incoming string name / alias.
	:param cmd:
	:return:
	"""
	cmd = cmd.lower()
	if cmd.startswith('!'):
		# Indicates a group command.
		cmd = cmd[1:]
		if cmd in _group_commands:
			return _group_commands[cmd]
		else:
			return None
	else:
		# Lack of '!' indicates a direct command
		if cmd in _direct_commands:
			return _direct_commands[cmd]
		else:
			return None


@command('help', direct=True)
def cmd_direct_help(target: str | None = None) -> CommandResponse:
	message = 'Available commands:\n'
	commands = []
	for cmd in _direct_commands.keys():
		if _direct_commands[cmd]._settings['auth']:
			commands.append(' '.join([cmd, '🔒']))
		else:
			commands.append(cmd)
	message += ' | '.join(commands)

	return CommandResponseSuccess(message)


@command('help', group=True)
def cmd_group_help(target: str | None = None) -> CommandResponse:
	message = 'Available commands:\n'
	commands = _group_commands.keys()
	message += '!' + ' | !'.join(commands)

	return CommandResponseSuccess(message)


@command('ping', direct=True)
def cmd_ping(target: str | None = None) -> CommandResponse:
	return CommandResponseSuccess(' '.join(['pong', target]))


@command('uptime', direct=True)
def cmd_uptime(target: str | None = None) -> CommandResponse:
	uptime = None
	try:
		with open('/proc/uptime', 'r') as f:
			uptime = float(f.read().split()[0])
	except FileNotFoundError:
		logging.error('Could not read uptime')
		return CommandResponseError('Could not read uptime')

	if uptime > 86400:
		days = int(uptime / 86400)
		hours = int((uptime - (days * 86400)) / 3600)
		return CommandResponseSuccess(f"Uptime: {days} days, {hours} hours")
	if uptime > 3600:
		hours = int(uptime / 3600)
		uptime = round(uptime % 3600)
		return CommandResponseSuccess(f"Uptime: {hours} hours, {uptime} seconds")

	return CommandResponseSuccess(f"Uptime: {uptime} seconds")


@command('cpu', direct=True)
def cmd_cpu(target: str | None = None) -> CommandResponse:
	temp = None
	try:
		with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
			temp = float(f.read()) / 1000
	except FileNotFoundError:
		logging.error('Could not read CPU temperature')

	load = os.getloadavg()
	load = round(load[1])
	if temp is not None:
		return CommandResponseSuccess(f"CPU: {load}% load and {temp}°C")
	else:
		return CommandResponseSuccess(f"CPU: {load}% load")


@command('temp', direct=True, group=True)
def cmd_temp(target: str | None = None) -> CommandResponse:
	temp = get_temperature()
	humidity = get_humidity()

	if temp is None:
		# Temperature not available.
		return CommandResponseError('Sorry, but no temperature is available right now.')
	elif humidity is None:
		# Temperature is, but humidity is not.
		fake_temp = round(temp * 1.8 + 32, 1)
		real_temp = round(temp, 1)
		return CommandResponseSuccess(f"Current temperature here is {real_temp}°C ({fake_temp}°F)")
	else:
		fake_temp = int(temp * 1.8 + 32)
		real_temp = int(temp)
		temps = f"{real_temp}°C ({fake_temp}°F)"
		pressure_change = get_pressure_change()

		if real_temp < 1:
			return CommandResponseSuccess(f"🥶 FREEZING! It's {temps} - Just stay home and get some hot chocolate!")

		if real_temp < 10:
			return CommandResponseSuccess(f"🧊 It's currently {temps} - Stay inside or bundle up!")

		if 10 <= real_temp < 18:
			if humidity > 80:
				return CommandResponseSuccess(f"☔ Damp and chilly, it's currently {temps}. Grab a waterproof coat.")

			if pressure_change == -1:
				return CommandResponseSuccess(f"☁️ A bit chilly at {temps} and rain may be on the horizon.")
			if pressure_change == 1:
				return CommandResponseSuccess(f"☀️ A bit chilly at {temps} but should be sunny.")
			return CommandResponseSuccess(f"A bit chilly right now at {temps}.")

		if 18 <= real_temp <= 24:
			if pressure_change == 0 or pressure_change == 1:
				if 30 <= humidity <= 60:
					return CommandResponseSuccess(f"☀️ Perfectly comfortable at {temps}.  Go out for a nice walk.")
				if humidity > 60:
					return CommandResponseSuccess(f"☁️ It's a comfortable {temps} but is rather sticky.")
			else:
				if 30 <= humidity <= 60:
					return CommandResponseSuccess(f"☁️ Perfectly comfortable at {temps} but it may storm soon.")
				if humidity > 60:
					return CommandResponseSuccess(f"☔ It's a comfortable {temps} but is rather wet out there.")

		if 24 < real_temp <= 29:
			hi = int(get_heat_index(real_temp, humidity))
			fake_hi = int(hi * 1.8 + 32)
			feels_like = f"{hi}°C ({fake_hi}°F)"

			if pressure_change == -1:
				return CommandResponseSuccess(f"☔ It's a hot and muggy {temps} and feels like {feels_like}.  Expect storms soon.")
			if hi > 32 and humidity > 70:
				return CommandResponseSuccess(f"🥵 It's a hot and muggy {temps} but feels like {feels_like}.  Take water & limit activity.")
			return CommandResponseSuccess(f"☀️ Warm and sunny at {temps}. Enjoy the heat!")

		if real_temp > 29:
			hi = int(get_heat_index(real_temp, humidity))
			fake_hi = int(hi * 1.8 + 32)
			if hi > 34 and humidity > 70:
				feels_like = f"{hi}°C ({fake_hi}°F"
				return CommandResponseSuccess(f"🔥 It's an oppressive {temps} & feels like {feels_like}. STAY SAFE AND HYDRATED!")

			if humidity <= 30:
				return CommandResponseSuccess(f"☀️ Hot and sunny at {temps} but very low humidity.  Enjoy the heat!")

			if pressure_change == -1:
				return CommandResponseSuccess(f"☀️ Hot and sunny at {temps} right now, but enjoy it while it lasts.  Storms may be on the horizon")

			return CommandResponseSuccess(f"☀️ Hot and sunny at {temps}. Enjoy the heat!")

		return CommandResponseSuccess(temps)


@command('pres', direct=True, group=True)
def cmd_pressure(target: str | None = None) -> CommandResponse:
	pressure = get_pressure()
	pressure_change = get_pressure_change()

	if pressure is None:
		return CommandResponseError('Sorry, but no pressure is available right now.')

	pressure = round(pressure, 2)

	if pressure_change == 1:
		return CommandResponseSuccess(f"Pressure has rose to {pressure}hPa!  Expect sunny weather.")

	if pressure_change == -1:
		return CommandResponseSuccess(f"Pressure has fallen to {pressure}hPa!  Expect rainy weather.")

	return CommandResponseSuccess(f"Pressure is a stable {pressure}hPa")


@command('humid', direct=True, group=True)
def cmd_humidity(target: str | None = None) -> CommandResponse:
	humidity = get_humidity()
	if humidity is None:
		return CommandResponseNoData('Sorry, but no humidity available')
	else:
		return CommandResponseSuccess('Current humidity here is %s%%' % round(humidity, 1))


@command('all', group=True, direct=True)
def cmd_all_sensors(target: str | None = None) -> CommandResponse:
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
		return CommandResponseSuccess('Current conditions here:\n' + ' | '.join(sensors))
	else:
		return CommandResponseNoData('Sorry, but no sensor data is available')


@command('forecast', direct=True, group=True)
def cmd_daily_forecast(target: str | None = None) -> CommandResponse:
	"""
	Fetches the daily weather forecast and broadcasts it over the mesh network.
	"""
	api = config.weather.openweather_api_key
	lat = config.location.lat
	lon = config.location.lon
	label = config.location.label

	if api == '':
		logging.error('No API key set for openweathermap.org, no forecast data available')
		return CommandResponseError('No API set for OpenWeatherMap.org, unable to fetch forecast data.')

	if lat is None:
		logging.error('No latitude set, unable to pull forecast data.')
		return CommandResponseError('No latitude set, unable to pull forecast data.')

	if lon is None:
		logging.error('No longitude set, unable to pull forecast data.')
		return CommandResponseError('No longitude set, unable to pull forecast data.')

	if label == '':
		header = 'Daily Forecast'
	else:
		header = f'Today for {label}'

	logging.debug('--- Running Daily Weather Forecast Fetch ---')
	try:
		# Initialize the weather client (it will read OPENWEATHERMAP_API_KEY)
		weather_client = WeatherForecast()
		forecast = weather_client.get_daily_forecast()

		if not forecast:
			print('Weather Forecast: Failed to retrieve data.')
			return CommandResponseError('Failed to retrieve forecast data.')

		low_f = round(forecast['low_temp'] * 1.8 + 32, 0)
		high_f = round(forecast['high_temp'] * 1.8 + 32, 0)

		# Format the message for broadcasting
		message = (
			f"{header}:\n{forecast['general_outlook']}\nLow/High: {forecast['low_temp']} / {forecast['high_temp']}°C\n({low_f} / {high_f}°F)"
		)
		return CommandResponseSuccess(message)
	except Exception as e:
		error_msg = f"Daily Weather: An error occurred during forecast fetching/broadcasting: {e}"
		print(f"Weather Forecast Error: {e}")
		return CommandResponseError(error_msg)


@command('alerts', direct=True, group=True)
def cmd_alerts(target: str | None = None) -> CommandResponse:
	lat = config.location.lat
	lon = config.location.lon

	if lat is None:
		logging.error('No latitude set, unable to pull forecast data.')
		return CommandResponseError('No latitude set, unable to pull weather alerts.')

	if lon is None:
		logging.error('No longitude set, unable to pull forecast data.')
		return CommandResponseError('No longitude set, unable to pull weather alerts.')

	if config.location.label == '':
		header = 'Weather Alerts'
	else:
		header = f'Alerts for {config.location.label}'

	logging.debug('--- Running Alerts Fetch ---')
	try:
		alerts = get_alerts(lat, lon)

		if len(alerts) == 0:
			return CommandResponseNoData('No weather alerts at this time.')

		return CommandResponseSuccess(f"{header}:\n" + '\n'.join(alerts))
	except Exception as e:
		error_msg = f"Weather Alerts: An error occurred during alert fetching/broadcasting: {e}"
		print(f"Weather Alerts Error: {e}")
		return CommandResponseError(error_msg)


@command('reboot', direct=True, auth=True)
def cmd_reboot(target: str | None = None):
	"""
	Instruct the raspberry pi to reboot.
	"""
	with open('/tmp/reboot', 'w') as f:
		f.write('reboot')

	return CommandResponseSuccess('Reboot scheduled')


@command('wake', direct=True, auth=True)
def cmd_wake(target: str | None = None):
	# Write a file to wake the device up
	with open('/tmp/wake', 'w') as f:
		f.write('wake')
	return CommandResponseSuccess('Device display should wake up shortly.')


@command('net', direct=True, auth=True)
def cmd_net(target: str | None = None):
	"""
	Get the net stats for the raspberry pi.
	:return:
	"""
	ip = get_local_ip()
	ssid = get_ssid()
	bars = get_bars()
	rate = get_rate()
	freq = get_frequency()
	return CommandResponseSuccess(f"IP: {ip}\nSSID: {ssid}\nBars: {bars}\nRate: {rate}\nFreq: {freq}")
