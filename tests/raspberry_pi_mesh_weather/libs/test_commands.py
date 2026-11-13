import pytest
from datetime import date

from raspberry_pi_mesh_weather.libs import commands
from raspberry_pi_mesh_weather.libs.commands import all_sensors, forecast, temp as temp_module


def _patch_readings(mocker, temp, humidity, pressure, change, label):
	mocker.patch.object(all_sensors, 'get_temperature', return_value=temp)
	mocker.patch.object(all_sensors, 'get_humidity', return_value=humidity)
	mocker.patch.object(all_sensors, 'get_pressure', return_value=pressure)
	mocker.patch.object(all_sensors, 'get_pressure_change', return_value=change)
	location = mocker.patch.object(all_sensors, 'config')
	location.location.label = label
	return commands.cmd_all_sensors(None)


def test_all_sensors_all_readings_stable(mocker):
	result = _patch_readings(mocker, 22.1, 45.3, 1012.3, 0, 'cbus')

	assert result.success is True
	assert result.has_data is True
	assert result.message == (
		'☀️ Weather in cbus:\n'
		'22.1°C (72°F) | 45.3% humidity | 1012.3 hPa (stable)'
	)


def test_all_sensors_pressure_rising(mocker):
	result = _patch_readings(mocker, 23.5, 40.0, 1012.7, 1, 'cbus')

	assert result.success is True
	assert result.message == (
		'☀️ Weather in cbus:\n'
		'23.5°C (74°F) | 40.0% humidity | 1012.7 hPa (rising)'
	)


def test_all_sensors_pressure_falling(mocker):
	result = _patch_readings(mocker, 21.0, 55.0, 1009.8, -1, 'cbus')

	assert result.success is True
	assert result.message == (
		'🌧️ Weather in cbus:\n'
		'21.0°C (70°F) | 55.0% humidity | 1009.8 hPa (falling)'
	)


def test_all_sensors_high_humidity_cloudy(mocker):
	result = _patch_readings(mocker, 29.5, 75.0, 1011.0, 0, 'cbus')

	assert result.success is True
	assert result.message == (
		'⛅ Weather in cbus:\n'
		'29.5°C (85°F) | 75.0% humidity | 1011.0 hPa (stable)'
	)


def test_all_sensors_freezing_takes_precedence(mocker):
	result = _patch_readings(mocker, -2.5, 30.0, 1012.0, 1, 'cbus')

	assert result.success is True
	assert result.message == (
		'🥶 Weather in cbus:\n'
		'-2.5°C (28°F) | 30.0% humidity | 1012.0 hPa (rising)'
	)


def test_all_sensors_missing_humidity(mocker):
	result = _patch_readings(mocker, 21.0, None, 1012.3, 0, 'cbus')

	assert result.success is True
	assert result.message == (
		'☀️ Weather in cbus:\n'
		'21.0°C (70°F) | 1012.3 hPa (stable)'
	)


def test_all_sensors_missing_location_label(mocker):
	result = _patch_readings(mocker, 20.0, 50.0, 1013.0, 0, '')

	assert result.success is True
	assert result.message == (
		'☀️ Current weather here:\n'
		'20.0°C (68°F) | 50.0% humidity | 1013.0 hPa (stable)'
	)


def test_all_sensors_missing_temperature(mocker):
	result = _patch_readings(mocker, None, 78.0, 1010.5, -1, 'cbus')

	assert result.success is True
	assert result.message == (
		'🌧️ Weather in cbus:\n'
		'78.0% humidity | 1010.5 hPa (falling)'
	)


def test_all_sensors_no_readings(mocker):
	result = _patch_readings(mocker, None, None, None, 0, 'cbus')

	assert result.success is True
	assert result.has_data is False
	assert result.message == 'Sorry, but no sensor data is available'


def _patch_temp_readings(mocker, temp, humidity, change):
	mocker.patch.object(temp_module, 'get_temperature', return_value=temp)
	mocker.patch.object(temp_module, 'get_humidity', return_value=humidity)
	mocker.patch.object(temp_module, 'get_pressure_change', return_value=change)
	return commands.cmd_temp(None)


def test_temp_not_available(mocker):
	result = _patch_temp_readings(mocker, None, 50.0, 0)

	assert result.success is False
	assert result.has_data is False
	assert result.message == 'Sorry, but no temperature is available right now.'


def test_temp_without_humidity(mocker):
	result = _patch_temp_readings(mocker, 22.5, None, 0)

	assert result.success is True
	assert result.has_data is True
	assert result.message == 'Current temperature here is 22.5°C (72.5°F)'


def test_temp_freezing(mocker):
	result = _patch_temp_readings(mocker, -3.4, 40.0, 0)

	assert result.success is True
	assert result.has_data is True
	assert result.message == "🥶 FREEZING! It's -3°C (26°F) - Just stay home and get some hot chocolate!"


def test_temp_cold_bundle_up(mocker):
	result = _patch_temp_readings(mocker, 5.0, 45.0, 0)

	assert result.success is True
	assert result.has_data is True
	assert result.message == "🧊 It's currently 5°C (41°F) - Stay inside or bundle up!"


def test_temp_chilly_damp(mocker):
	result = _patch_temp_readings(mocker, 12.0, 90.0, 0)

	assert result.success is True
	assert result.has_data is True
	assert result.message == "☔ Damp and chilly, it's currently 12°C (54°F). Grab a waterproof coat."


def test_temp_chilly_falling_pressure(mocker):
	result = _patch_temp_readings(mocker, 12.0, 45.0, -1)

	assert result.success is True
	assert result.has_data is True
	assert result.message == "☁️ A bit chilly at 12°C (54°F) and rain may be on the horizon."


def test_temp_chilly_rising_pressure(mocker):
	result = _patch_temp_readings(mocker, 12.0, 45.0, 1)

	assert result.success is True
	assert result.has_data is True
	assert result.message == "☀️ A bit chilly at 12°C (54°F) but should be sunny."


def test_temp_chilly_stable(mocker):
	result = _patch_temp_readings(mocker, 12.0, 45.0, 0)

	assert result.success is True
	assert result.has_data is True
	assert result.message == "A bit chilly right now at 12°C (54°F)."


def test_temp_comfortable_stable(mocker):
	result = _patch_temp_readings(mocker, 22.0, 50.0, 0)

	assert result.success is True
	assert result.has_data is True
	assert result.message == "☀️ Perfectly comfortable at 22°C (72°F).  Go out for a nice walk."


def test_temp_comfortable_stable_sticky(mocker):
	result = _patch_temp_readings(mocker, 22.0, 80.0, 0)

	assert result.success is True
	assert result.has_data is True
	assert result.message == "☁️ It's a comfortable 22°C (72°F) but is rather sticky."


def test_temp_comfortable_stable_dry(mocker):
	result = _patch_temp_readings(mocker, 22.0, 20.0, 0)

	assert result.success is True
	assert result.has_data is True
	assert result.message == "☀️ Perfectly comfortable and dry at 22°C (72°F).  Go out for a nice walk."


def test_temp_comfortable_falling_storm(mocker):
	result = _patch_temp_readings(mocker, 22.0, 50.0, -1)

	assert result.success is True
	assert result.has_data is True
	assert result.message == "☁️ Perfectly comfortable at 22°C (72°F) but it may storm soon."


def test_temp_comfortable_falling_wet(mocker):
	result = _patch_temp_readings(mocker, 22.0, 80.0, -1)

	assert result.success is True
	assert result.has_data is True
	assert result.message == "☔ It's a comfortable 22°C (72°F) but is rather wet out there."


def test_temp_comfortable_falling_dry(mocker):
	result = _patch_temp_readings(mocker, 22.0, 20.0, -1)

	assert result.success is True
	assert result.has_data is True
	assert result.message == "☁️ Comfortable and dry at 22°C (72°F) but it may storm soon."


def test_temp_warm_sunny(mocker):
	result = _patch_temp_readings(mocker, 26.0, 40.0, 0)

	assert result.success is True
	assert result.has_data is True
	assert result.message == "☀️ Warm and sunny at 26°C (79°F). Enjoy the heat!"


def test_temp_warm_muggy(mocker):
	result = _patch_temp_readings(mocker, 25.0, 80.0, 0)

	assert result.success is True
	assert result.has_data is True
	assert result.message == "☁️ Warm and muggy at 25°C (77°F).  It feels a bit like 25°C (77°F)."


def test_temp_warm_muggy_severe(mocker):
	result = _patch_temp_readings(mocker, 28.9, 90.0, 0)

	assert result.success is True
	assert result.has_data is True
	assert result.message == "🥵 It's a hot and muggy 29°C (84°F) but feels like 37°C (99°F).  Take water & limit activity."


def test_temp_warm_falling_pressure_storm(mocker):
	result = _patch_temp_readings(mocker, 26.0, 80.0, -1)

	assert result.success is True
	assert result.has_data is True
	assert result.message == "☔ It's a hot and muggy 26°C (79°F) and feels like 26°C (79°F).  Expect storms soon."


def test_temp_oppressive_heat(mocker):
	result = _patch_temp_readings(mocker, 35.0, 75.0, 0)

	assert result.success is True
	assert result.has_data is True
	assert result.message == "🔥 It's an oppressive 35°C (95°F) & feels like 53°C (127°F). STAY SAFE AND HYDRATED!"


def test_temp_hot_low_humidity(mocker):
	result = _patch_temp_readings(mocker, 33.0, 25.0, 0)

	assert result.success is True
	assert result.has_data is True
	assert result.message == "☀️ Hot and sunny at 33°C (91°F) but very low humidity.  Enjoy the heat!"


def test_temp_hot_storm(mocker):
	result = _patch_temp_readings(mocker, 31.0, 50.0, -1)

	assert result.success is True
	assert result.has_data is True
	assert result.message == "☀️ Hot and sunny at 31°C (88°F) right now, but enjoy it while it lasts.  Storms may be on the horizon."


def test_temp_hot_sunny(mocker):
	result = _patch_temp_readings(mocker, 31.0, 50.0, 0)

	assert result.success is True
	assert result.has_data is True
	assert result.message == "☀️ Hot and sunny at 31°C (88°F). Enjoy the heat!"


def test_heat_index_below_threshold_returns_temp():
	# The Rothfusz regression is only applicable from 26.7°C (80°F) up.
	assert commands.get_heat_index(25.0, 50.0) == 25.0


def test_heat_index_28_9c_90rh():
	assert commands.get_heat_index(28.9, 90.0) == pytest.approx(36.73, abs=0.01)


def test_heat_index_35c_75rh():
	assert commands.get_heat_index(35.0, 75.0) == pytest.approx(53.33, abs=0.01)


# --- forecast --------------------------------------------------------


def _patch_forecast_cmd(mocker, entries, label='cbus', api='test-api-key', today=None):
	"""
	Invoke cmd_daily_forecast with a mocked WeatherForecast that returns `entries`.
	Patches config, WeatherForecast, and (optionally) date.today.
	"""
	config = mocker.patch.object(forecast, 'config')
	config.weather.openweather_api_key = api
	config.location.lat = 39.96
	config.location.lon = -83.0
	config.location.label = label
	weather = mocker.patch.object(forecast, 'WeatherForecast')
	weather.return_value.get_daily_forecast.return_value = entries
	if today is not None:
		class _FakeDate(date):
			@classmethod
			def today(cls):
				return today
		mocker.patch.object(forecast, 'date', _FakeDate)
	return commands.cmd_daily_forecast(None)


def test_forecast_command_evening_spills_into_tomorrow(mocker):
	entries = [
		{'hour': 21, 'date': '2026-11-13', 'temp': 9.54, 'icon': '🌧️', 'description': 'light rain'},
		{'hour': 0, 'date': '2026-11-14', 'temp': 7.40, 'icon': '🌧️', 'description': 'light rain'},
		{'hour': 3, 'date': '2026-11-14', 'temp': 4.81, 'icon': '☁️', 'description': 'overcast clouds'},
		{'hour': 6, 'date': '2026-11-14', 'temp': 4.82, 'icon': '🌧️', 'description': 'light rain'},
		{'hour': 9, 'date': '2026-11-14', 'temp': 4.77, 'icon': '🌧️', 'description': 'light rain'},
	]
	result = _patch_forecast_cmd(mocker, entries, today=date(2026, 11, 13))

	assert result.success is True
	assert result.has_data is True
	assert result.message == (
		'Forecast for cbus:\n'
		'🌧️  9 PM: light rain, 9.5°C (49°F)\n'
		'🌧️  12 AM: light rain, 7.4°C (45°F)\n'
		'☁️  3 AM: overcast clouds, 4.8°C (41°F)\n'
		'🌧️  6 AM: light rain, 4.8°C (41°F)\n'
		'🌧️  9 AM: light rain, 4.8°C (41°F)\n'
		'Low/High: 5°C / 10°C (41°F / 50°F)'
	)


def test_forecast_command_morning_all_today(mocker):
	entries = [
		{'hour': 9, 'date': '2026-11-13', 'temp': 9.54, 'icon': '🌧️', 'description': 'light rain'},
		{'hour': 12, 'date': '2026-11-13', 'temp': 3.98, 'icon': '☁️', 'description': 'broken clouds'},
		{'hour': 15, 'date': '2026-11-13', 'temp': 10.08, 'icon': '☁️', 'description': 'broken clouds'},
	]
	result = _patch_forecast_cmd(mocker, entries, today=date(2026, 11, 13))

	assert result.success is True
	assert result.message == (
		'Forecast for cbus:\n'
		'🌧️  9 AM: light rain, 9.5°C (49°F)\n'
		'☁️  12 PM: broken clouds, 4.0°C (39°F)\n'
		'☁️  3 PM: broken clouds, 10.1°C (50°F)\n'
		'Low/High: 4°C / 10°C (39°F / 50°F)'
	)


def test_forecast_command_missing_label_uses_plain_header(mocker):
	entries = [{'hour': 9, 'date': '2026-11-13', 'temp': 9.54, 'icon': '☀️', 'description': 'clear sky'}]
	result = _patch_forecast_cmd(mocker, entries, label='', today=date(2026, 11, 13))

	assert result.success is True
	assert result.message == (
		'Forecast:\n'
		'☀️  9 AM: clear sky, 9.5°C (49°F)\n'
		'Low/High: 10°C / 10°C (50°F / 50°F)'
	)


def test_forecast_command_no_api_key(mocker):
	config = mocker.patch.object(forecast, 'config')
	config.weather.openweather_api_key = ''
	config.location.lat = 39.96
	config.location.lon = -83.0
	config.location.label = 'cbus'
	result = commands.cmd_daily_forecast(None)

	assert result.success is False
	assert result.has_data is False
	assert result.message == 'No API set for OpenWeatherMap.org, unable to fetch forecast data.'


def test_forecast_command_empty_entries(mocker):
	config = mocker.patch.object(forecast, 'config')
	config.weather.openweather_api_key = 'test-api-key'
	config.location.lat = 39.96
	config.location.lon = -83.0
	config.location.label = 'cbus'
	mocker.patch.object(forecast, 'WeatherForecast').return_value.get_daily_forecast.return_value = []
	result = commands.cmd_daily_forecast(None)

	assert result.success is False
	assert result.has_data is False
	assert result.message == 'Failed to retrieve forecast data.'
