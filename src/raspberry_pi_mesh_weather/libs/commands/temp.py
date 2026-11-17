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

from .handler import command, CommandResponse, CommandResponseError, CommandResponseSuccess
from raspberry_pi_mesh_weather.libs.humidity import get_humidity
from raspberry_pi_mesh_weather.libs.icon_map import get_icon
from raspberry_pi_mesh_weather.libs.pressure import get_pressure_change
from raspberry_pi_mesh_weather.libs.temperature import get_temperature


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


@command('temp', direct=True, group=True)
@command('temperature', direct=True, group=True)
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
		# Round once and reuse the same values for both display and banding,
		# so borderline temperatures (e.g. 24.9°C) get the correct band.
		real_temp = round(temp)
		fake_temp = round(temp * 1.8 + 32)
		temps = f"{real_temp}°C ({fake_temp}°F)"
		pressure_change = get_pressure_change()

		# Resolve the icons used in the bands below through the active icon style.
		# (see libs/icon_map.py).
		sun_icon = get_icon('sun')
		cloud_icon = get_icon('cloud')
		rain_icon = get_icon('rain')
		freezing_icon = get_icon('freezing')
		snow_icon = get_icon('snow')
		heat_icon = get_icon('heat')
		fire_icon = get_icon('fire')

		if real_temp < 1:
			return CommandResponseSuccess(f"{freezing_icon} FREEZING! It's {temps} - Just stay home and get some hot chocolate!")

		if real_temp < 10:
			return CommandResponseSuccess(f"{snow_icon} It's currently {temps} - Stay inside or bundle up!")

		if 10 <= real_temp < 18:
			if humidity > 80:
				return CommandResponseSuccess(f"{rain_icon} Damp and chilly, it's currently {temps}. Grab a waterproof coat.")

			if pressure_change == -1:
				return CommandResponseSuccess(f"{cloud_icon} A bit chilly at {temps} and rain may be on the horizon.")
			if pressure_change == 1:
				return CommandResponseSuccess(f"{sun_icon} A bit chilly at {temps} but should be sunny.")
			return CommandResponseSuccess(f"A bit chilly right now at {temps}.")

		if 18 <= real_temp <= 24:
			if pressure_change == -1:
				if 30 <= humidity <= 60:
					return CommandResponseSuccess(f"{cloud_icon} Perfectly comfortable at {temps} but it may storm soon.")
				if humidity > 60:
					return CommandResponseSuccess(f"{rain_icon} It's a comfortable {temps} but is rather wet out there.")
				return CommandResponseSuccess(f"{cloud_icon} Comfortable and dry at {temps} but it may storm soon.")
			if pressure_change is None:
				# No local pressure data to base a trend on.
				return CommandResponseSuccess(f"It's perfectly comfortable at {temps}.")
			if 30 <= humidity <= 60:
				return CommandResponseSuccess(f"{sun_icon} Perfectly comfortable at {temps}.  Go out for a nice walk.")
			if humidity > 60:
				return CommandResponseSuccess(f"{cloud_icon} It's a comfortable {temps} but is rather sticky.")
			return CommandResponseSuccess(f"{sun_icon} Perfectly comfortable and dry at {temps}.  Go out for a nice walk.")

		if 24 < real_temp <= 29:
			hi = round(get_heat_index(real_temp, humidity))
			fake_hi = round(hi * 1.8 + 32)
			feels_like = f"{hi}°C ({fake_hi}°F)"

			if pressure_change == -1:
				return CommandResponseSuccess(f"{rain_icon} It's a hot and muggy {temps} and feels like {feels_like}.  Expect storms soon.")
			if humidity > 70:
				if hi > 32:
					return CommandResponseSuccess(f"{heat_icon} It's a hot and muggy {temps} but feels like {feels_like}.  Take water & limit activity.")
				return CommandResponseSuccess(f"{cloud_icon} Warm and muggy at {temps}.  It feels a bit like {feels_like}.")
			return CommandResponseSuccess(f"{sun_icon} Warm and sunny at {temps}. Enjoy the heat!")

		if real_temp > 29:
			hi = round(get_heat_index(real_temp, humidity))
			fake_hi = round(hi * 1.8 + 32)
			feels_like = f"{hi}°C ({fake_hi}°F)"

			if hi > 34 and humidity > 70:
				return CommandResponseSuccess(f"{fire_icon} It's an oppressive {temps} & feels like {feels_like}. STAY SAFE AND HYDRATED!")

			if humidity <= 30:
				return CommandResponseSuccess(f"{sun_icon} Hot and sunny at {temps} but very low humidity.  Enjoy the heat!")

			if pressure_change == -1:
				return CommandResponseSuccess(f"{sun_icon} Hot and sunny at {temps} right now, but enjoy it while it lasts.  Storms may be on the horizon.")

			return CommandResponseSuccess(f"{sun_icon} Hot and sunny at {temps}. Enjoy the heat!")

		return CommandResponseSuccess(temps)
