from datetime import datetime, timezone

import pytest

from raspberry_pi_mesh_weather.libs import sun as sun_lib
from raspberry_pi_mesh_weather.libs import commands
from raspberry_pi_mesh_weather.libs import icon_map
from raspberry_pi_mesh_weather.libs.commands import (
	all_sensors,
	forecast,
	sun as sun_command_module,
	temp as temp_module,
	wind as wind_command_module,
)
from raspberry_pi_mesh_weather.libs import open_weather_map
from raspberry_pi_mesh_weather.libs.system_state import state
from raspberry_pi_mesh_weather.libs.temperature import get_temperature
from raspberry_pi_mesh_weather.libs.pressure import get_pressure, get_pressure_change
from raspberry_pi_mesh_weather.libs.humidity import get_humidity
from raspberry_pi_mesh_weather.libs.wind import get_wind_compass, get_wind_gust, get_wind_speed


def _patch_readings(
	mocker,
	temp,
	humidity,
	pressure,
	change,
	label,
	wind_speed=None,
	wind_compass=None,
	sun_event=None,
):
	mocker.patch.object(all_sensors, 'get_temperature', return_value=temp)
	mocker.patch.object(all_sensors, 'get_humidity', return_value=humidity)
	mocker.patch.object(all_sensors, 'get_pressure', return_value=pressure)
	mocker.patch.object(all_sensors, 'get_pressure_change', return_value=change)
	mocker.patch.object(all_sensors, 'get_wind_speed', return_value=wind_speed)
	mocker.patch.object(all_sensors, 'get_wind_compass', return_value=wind_compass)
	location = mocker.patch.object(all_sensors, 'config')
	location.location.label = label
	# The all command also reads the next sun event from the sun library; patch
	# it (default None -> no sun item) and pin the module's clock to UTC so
	# sun.format_time() is deterministic.
	sun_mod = all_sensors.sun
	mocker.patch.object(sun_mod, 'get_next_sun_event', return_value=sun_event)
	class _FakeDatetime(datetime):
		@classmethod
		def fromtimestamp(cls, ts, *args, **kwargs):
			return datetime.fromtimestamp(ts, tz=timezone.utc)
	mocker.patch.object(sun_mod, 'datetime', _FakeDatetime)
	return commands.cmd_all_sensors(None)


def test_all_sensors_all_readings_stable(mocker):
	result = _patch_readings(mocker, 22.1, 45.3, 1012.3, 0, 'cbus', wind_speed=4.5, wind_compass='NNW')

	assert result.success is True
	assert result.has_data is True
	assert 'Weather in cbus:' in result.message
	assert '22.1°C (72°F)' in result.message
	assert '45.3% humidity' in result.message
	assert '1012.3 hPa (stable)' in result.message
	assert 'wind 4 m/s NNW' in result.message


def test_all_sensors_pressure_rising(mocker):
	result = _patch_readings(mocker, 23.5, 40.0, 1012.7, 1, 'cbus', wind_speed=4.5, wind_compass='NNW')

	assert result.success is True
	assert '1012.7 hPa (rising)' in result.message


def test_all_sensors_pressure_falling(mocker):
	result = _patch_readings(mocker, 21.0, 55.0, 1009.8, -1, 'cbus', wind_speed=4.5, wind_compass='NNW')

	assert result.success is True
	assert '1009.8 hPa (falling)' in result.message


def test_all_sensors_high_humidity_cloudy(mocker):
	result = _patch_readings(mocker, 29.5, 75.0, 1011.0, 0, 'cbus', wind_speed=4.5, wind_compass='NNW')

	assert result.success is True
	assert '75.0% humidity' in result.message


def test_all_sensors_freezing_takes_precedence(mocker):
	result = _patch_readings(mocker, -2.5, 30.0, 1012.0, 1, 'cbus', wind_speed=4.5, wind_compass='NNW')

	assert result.success is True
	assert 'Weather in cbus:' in result.message
	assert '-2.5°C (28°F)' in result.message
	assert '30.0% humidity' in result.message
	assert '1012.0 hPa (rising)' in result.message
	assert 'wind 4 m/s NNW' in result.message


def test_all_sensors_missing_humidity(mocker):
	result = _patch_readings(mocker, 21.0, None, 1012.3, 0, 'cbus', wind_speed=4.5, wind_compass='NNW')

	assert result.success is True
	assert 'Weather in cbus:' in result.message
	assert '21.0°C (70°F)' in result.message
	assert 'humidity' not in result.message
	assert '1012.3 hPa (stable)' in result.message
	assert 'wind 4 m/s NNW' in result.message


def test_all_sensors_missing_location_label(mocker):
	result = _patch_readings(mocker, 20.0, 50.0, 1013.0, 0, '', wind_speed=4.5, wind_compass='NNW')

	assert result.success is True
	assert 'Current weather here:' in result.message
	assert '20.0°C (68°F)' in result.message
	assert '50.0% humidity' in result.message
	assert '1013.0 hPa (stable)' in result.message
	assert 'wind 4 m/s NNW' in result.message


def test_all_sensors_missing_temperature(mocker):
	result = _patch_readings(mocker, None, 78.0, 1010.5, -1, 'cbus', wind_speed=4.5, wind_compass='NNW')

	assert result.success is True
	assert 'Weather in cbus:' in result.message
	assert '°C' not in result.message
	assert '°F' not in result.message
	assert '78.0% humidity' in result.message
	assert '1010.5 hPa (falling)' in result.message
	assert 'wind 4 m/s NNW' in result.message


def test_all_sensors_no_readings(mocker):
	result = _patch_readings(mocker, None, None, None, 0, 'cbus')

	assert result.success is True
	assert result.has_data is False
	assert result.message == 'Sorry, but no sensor data is available'


def test_all_sensors_no_pressure_change(mocker):
	result = _patch_readings(mocker, 22.1, 45.3, 1012.3, None, 'cbus', wind_speed=4.5, wind_compass='NNW')

	assert result.success is True
	assert result.has_data is True
	assert result.message == (
		'☀ Weather in cbus:\n'
		'22.1°C (72°F) | 45.3% humidity | 1012.3 hPa | wind 4 m/s NNW'
	)


def test_all_sensors_wind_without_compass(mocker):
	result = _patch_readings(mocker, 22.1, 45.3, 1012.3, 0, 'cbus', wind_speed=4.5, wind_compass=None)

	assert result.success is True
	assert result.has_data is True
	assert result.message == (
		'☀ Weather in cbus:\n'
		'22.1°C (72°F) | 45.3% humidity | 1012.3 hPa (stable) | wind 4 m/s'
	)


# Columbus fixture epochs, pinned to UTC by _patch_readings: 12:13 PM
# sunrise, 10:18 PM sunset.
_SUNRISE = 1794485621
_SUNSET = 1794521926


def test_all_sensors_daytime_shows_sunset(mocker):
	result = _patch_readings(mocker, 22.1, 45.3, 1012.3, 0, 'cbus', wind_speed=4.5,
							wind_compass='NNW', sun_event={'name': 'sunset', 'dt': _SUNSET})

	assert result.success is True
	assert result.has_data is True
	assert result.message == (
		'☀ Weather in cbus:\n'
		'22.1°C (72°F) | 45.3% humidity | 1012.3 hPa (stable) | wind 4 m/s NNW | sunset 10:18 PM'
	)


def test_all_sensors_pre_dawn_shows_sunrise(mocker):
	result = _patch_readings(mocker, 22.1, 45.3, 1012.3, 0, 'cbus', wind_speed=4.5,
							wind_compass='NNW', sun_event={'name': 'sunrise', 'dt': _SUNRISE})

	assert result.success is True
	assert result.has_data is True
	assert result.message == (
		'☀ Weather in cbus:\n'
		'22.1°C (72°F) | 45.3% humidity | 1012.3 hPa (stable) | wind 4 m/s NNW | sunrise 12:13 PM'
	)


def test_all_sensors_no_wind_and_sun(mocker):
	# Even with a sun event, a missing wind still drops only the wind item.
	result = _patch_readings(mocker, 22.1, 45.3, 1012.3, 0, 'cbus', wind_speed=None,
							wind_compass=None, sun_event={'name': 'sunset', 'dt': _SUNSET})

	assert result.success is True
	assert result.has_data is True
	assert result.message == (
		'☀ Weather in cbus:\n'
		'22.1°C (72°F) | 45.3% humidity | 1012.3 hPa (stable) | sunset 10:18 PM'
	)


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


def test_temp_comfortable_no_pressure_change(mocker):
	result = _patch_temp_readings(mocker, 22.0, 50.0, None)

	assert result.success is True
	assert result.has_data is True
	assert result.message == "It's perfectly comfortable at 22°C (72°F)."


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


def _patch_forecast_cmd(mocker, entries, label='cbus', api='test-api-key'):
	"""
	Invoke cmd_daily_forecast with a mocked OpenWeatherMap that returns `entries`.
	"""
	config = mocker.patch.object(forecast, 'config')
	config.weather.openweather_api_key = api
	config.location.lat = 39.96
	config.location.lon = -83.0
	config.location.label = label
	weather = mocker.patch.object(forecast, 'OpenWeatherMap')
	weather.return_value.get_daily_forecast.return_value = entries
	return commands.cmd_daily_forecast(None)


def test_forecast_command_evening_spills_into_tomorrow(mocker):
	entries = [
		{'hour': 21, 'date': '2026-11-13', 'temp': 9.54, 'icon': '🌧️', 'description': 'light rain'},
		{'hour': 0, 'date': '2026-11-14', 'temp': 7.40, 'icon': '🌧️', 'description': 'light rain'},
		{'hour': 3, 'date': '2026-11-14', 'temp': 4.81, 'icon': '☁️', 'description': 'overcast clouds'},
		{'hour': 6, 'date': '2026-11-14', 'temp': 4.82, 'icon': '🌧️', 'description': 'light rain'},
		{'hour': 9, 'date': '2026-11-14', 'temp': 4.77, 'icon': '🌧️', 'description': 'light rain'},
	]
	result = _patch_forecast_cmd(mocker, entries)

	assert result.success is True
	assert result.has_data is True
	assert result.message == (
		'Forecast for cbus: Light rain until 3A\n'
		'🌧️  9P: 10°C/49°F\n'
		'🌧️  12A: 7°C/45°F\n'
		'☁️  3A: 5°C/41°F\n'
		'🌧️  6A: 5°C/41°F\n'
		'🌧️  9A: 5°C/41°F'
	)


def test_forecast_command_morning_all_today(mocker):
	entries = [
		{'hour': 9, 'date': '2026-11-13', 'temp': 9.54, 'icon': '🌧️', 'description': 'light rain'},
		{'hour': 12, 'date': '2026-11-13', 'temp': 3.98, 'icon': '☁️', 'description': 'broken clouds'},
		{'hour': 15, 'date': '2026-11-13', 'temp': 10.08, 'icon': '☁️', 'description': 'broken clouds'},
	]
	result = _patch_forecast_cmd(mocker, entries)

	assert result.success is True
	assert result.message == (
		'Forecast for cbus: Light rain until 12P\n'
		'🌧️  9A: 10°C/49°F\n'
		'☁️  12P: 4°C/39°F\n'
		'☁️  3P: 10°C/50°F'
	)


def test_forecast_command_missing_label_uses_plain_header(mocker):
	entries = [{'hour': 9, 'date': '2026-11-13', 'temp': 9.54, 'icon': '☀️', 'description': 'clear sky'}]
	result = _patch_forecast_cmd(mocker, entries, label='')

	assert result.success is True
	assert result.message == (
		'Forecast: Clear sky\n'
		'☀️  9A: 10°C/49°F'
	)


def test_forecast_command_around_when_calm_then_active(mocker):
	# Calm now with rain arriving -> lead with the incoming weather.
	entries = [
		{'hour': 22, 'date': '2026-11-13', 'temp': 2.0, 'icon': '☀️', 'description': 'clear sky'},
		{'hour': 7, 'date': '2026-11-14', 'temp': 4.3, 'icon': '🌧️', 'description': 'light rain'},
		{'hour': 10, 'date': '2026-11-14', 'temp': 7.3, 'icon': '🌧️', 'description': 'light rain'},
	]
	result = _patch_forecast_cmd(mocker, entries)

	assert result.success is True
	assert result.message == (
		'Forecast for cbus: Light rain around 7A\n'
		'☀️  10P: 2°C/36°F\n'
		'🌧️  7A: 4°C/40°F\n'
		'🌧️  10A: 7°C/45°F'
	)


def test_forecast_command_active_then_calm_uses_until(mocker):
	# Active now clearing to calm -> single-state "until" phrasing, not "around".
	entries = [
		{'hour': 21, 'date': '2026-11-13', 'temp': 5.0, 'icon': '🌧️', 'description': 'light rain'},
		{'hour': 7, 'date': '2026-11-14', 'temp': 1.0, 'icon': '☀️', 'description': 'clear sky'},
	]
	result = _patch_forecast_cmd(mocker, entries)

	assert result.success is True
	assert result.message == (
		'Forecast for cbus: Light rain until 7A\n'
		'🌧️  9P: 5°C/41°F\n'
		'☀️  7A: 1°C/34°F'
	)


def test_forecast_command_single_state(mocker):
	entries = [
		{'hour': 9, 'date': '2026-11-13', 'temp': 9.54, 'icon': '☀️', 'description': 'clear sky'},
		{'hour': 12, 'date': '2026-11-13', 'temp': 8.1, 'icon': '☀️', 'description': 'clear sky'},
		{'hour': 15, 'date': '2026-11-13', 'temp': 9.9, 'icon': '☀️', 'description': 'clear sky'},
	]
	result = _patch_forecast_cmd(mocker, entries)

	assert result.success is True
	assert result.message == (
		'Forecast for cbus: Clear sky\n'
		'☀️  9A: 10°C/49°F\n'
		'☀️  12P: 8°C/47°F\n'
		'☀️  3P: 10°C/50°F'
	)


def test_forecast_command_skips_calm_to_first_notable(mocker):
	# Calm now, calm again, then a noteworthy event -> skip calm states and
	# lead with the first active state (not the second calm one).
	entries = [
		{'hour': 21, 'date': '2026-11-13', 'temp': 8.0, 'icon': '☀️', 'description': 'clear sky'},
		{'hour': 0, 'date': '2026-11-14', 'temp': 7.0, 'icon': '☁️', 'description': 'broken clouds'},
		{'hour': 3, 'date': '2026-11-14', 'temp': 4.0, 'icon': '🌧️', 'description': 'light rain'},
		{'hour': 6, 'date': '2026-11-14', 'temp': 4.0, 'icon': '🌧️', 'description': 'light rain'},
	]
	result = _patch_forecast_cmd(mocker, entries)

	assert result.success is True
	assert result.message == (
		'Forecast for cbus: Light rain around 3A\n'
		'☀️  9P: 8°C/46°F\n'
		'☁️  12A: 7°C/45°F\n'
		'🌧️  3A: 4°C/39°F\n'
		'🌧️  6A: 4°C/39°F'
	)


def test_forecast_command_all_calm_reports_current(mocker):
	# No noteworthy weather at all -> just describe the current state.
	entries = [
		{'hour': 21, 'date': '2026-11-13', 'temp': 8.0, 'icon': '☀️', 'description': 'clear sky'},
		{'hour': 0, 'date': '2026-11-14', 'temp': 7.0, 'icon': '☁️', 'description': 'few clouds'},
		{'hour': 3, 'date': '2026-11-14', 'temp': 6.0, 'icon': '☁️', 'description': 'overcast clouds'},
	]
	result = _patch_forecast_cmd(mocker, entries)

	assert result.success is True
	assert result.message == (
		'Forecast for cbus: Clear sky\n'
		'☀️  9P: 8°C/46°F\n'
		'☁️  12A: 7°C/45°F\n'
		'☁️  3A: 6°C/43°F'
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
	mocker.patch.object(forecast, 'OpenWeatherMap').return_value.get_daily_forecast.return_value = []
	result = commands.cmd_daily_forecast(None)

	assert result.success is False
	assert result.has_data is False
	assert result.message == 'Failed to retrieve forecast data.'


# --- icons --------------------------------------------------------
#
# Minimal diagnostic command: returns every weather glyph of the active
# icon style, so the sender can verify which icons render on their own
# device.


def test_icons_default_compatible_style():
	# No patching: honours the shipped default ('compatible') from the
	# dataclass / config.yaml.
	result = commands.cmd_icons(None)

	assert result.success is True
	assert result.has_data is True
	assert result.message == ' '.join(
		icon_map.get_icon(name) for name in icon_map.STANDARD_ICON_NAMES
	)
	# Glyphs stay within the widely-supported ranges: the warning sign
	# (U+26A0) is the fallback for alert names with no basic-symbol
	# equivalent, and the snowflake (U+2744) appears once for snow and
	# twice for freezing.
	assert len(result.message) <= 130


def test_icons_compatible_style(mocker):
	mocker.patch.object(icon_map.config.general, 'icon_style', 'compatible')
	result = commands.cmd_icons(None)

	assert result.success is True
	assert result.has_data is True
	assert result.message == ' '.join(
		icon_map.get_icon(name) for name in icon_map.STANDARD_ICON_NAMES
	)


def test_icons_modern_style(mocker):
	mocker.patch.object(icon_map.config.general, 'icon_style', 'modern')
	result = commands.cmd_icons(None)

	assert result.success is True
	assert result.has_data is True
	assert result.message == ' '.join(
		icon_map.get_icon(name) for name in icon_map.STANDARD_ICON_NAMES
	)
	# Colour emoji in the modern set, VS included.
	assert (chr(0x1F300) + chr(0xFE0F)) in result.message  # cyclone
	assert len(result.message) <= 130


# --- current-conditions fallback -------------------------------------------
#
# The sensor getters fall back to OpenWeatherMap current conditions when the
# local sensor reading is unavailable (the state entry is None).

OWM_CURRENT = {
	'temp': 12.0,
	'feels_like': 10.0,
	'pressure': 1005.4,
	'humidity': 81,
	'dt': 1794517200,
}


def test_get_temperature_prefers_sensor(mocker):
	mocker.patch.object(state, 'get', return_value=18.5)
	owm = mocker.patch.object(open_weather_map, 'get_current_conditions', return_value=OWM_CURRENT)
	assert get_temperature() == 18.5
	owm.assert_not_called()


def test_get_temperature_falls_back_to_owm(mocker):
	mocker.patch.object(state, 'get', return_value=None)
	owm = mocker.patch.object(open_weather_map, 'get_current_conditions', return_value=OWM_CURRENT)
	assert get_temperature() == 12.0
	owm.assert_called_once()


def test_get_temperature_none_when_both_down(mocker):
	mocker.patch.object(state, 'get', return_value=None)
	mocker.patch.object(open_weather_map, 'get_current_conditions', return_value=None)
	assert get_temperature() is None


def test_get_pressure_falls_back_to_owm(mocker):
	mocker.patch.object(state, 'get', return_value=None)
	mocker.patch.object(open_weather_map, 'get_current_conditions', return_value=OWM_CURRENT)
	assert get_pressure() == 1005.4


def test_get_humidity_falls_back_to_owm(mocker):
	mocker.patch.object(state, 'get', return_value=None)
	mocker.patch.object(open_weather_map, 'get_current_conditions', return_value=OWM_CURRENT)
	assert get_humidity() == 81


# --- pressure change --------------------------------------------------------


def test_get_pressure_change_none_without_local_data(mocker):
	mocker.patch.object(state, 'get_earliest', return_value=None)
	mocker.patch.object(state, 'get', return_value=None)
	assert get_pressure_change() is None


def test_get_pressure_change_rising(mocker):
	mocker.patch.object(state, 'get_earliest', return_value=1009.0)
	mocker.patch.object(state, 'get', return_value=1012.0)
	assert get_pressure_change() == 1.0


def test_get_pressure_change_falling(mocker):
	mocker.patch.object(state, 'get_earliest', return_value=1012.0)
	mocker.patch.object(state, 'get', return_value=1009.0)
	assert get_pressure_change() == -1.0


def test_get_pressure_change_stable(mocker):
	mocker.patch.object(state, 'get_earliest', return_value=1010.0)
	mocker.patch.object(state, 'get', return_value=1010.5)
	assert get_pressure_change() == 0.0


def test_all_uses_owm_when_sensors_down(mocker):
	mocker.patch.object(state, 'get', return_value=None)
	mocker.patch.object(state, 'get_earliest', return_value=None)
	mocker.patch.object(open_weather_map, 'get_current_conditions', return_value=OWM_CURRENT)
	location = mocker.patch.object(all_sensors, 'config')
	location.location.label = 'cbus'
	result = commands.cmd_all_sensors(None)

	assert result.success is True
	assert result.has_data is True
	assert result.message == (
		'☀ Weather in cbus:\n'
		'12.0°C (54°F) | 81.0% humidity | 1005.4 hPa'
	)


def test_temp_uses_owm_when_sensor_down(mocker):
	mocker.patch.object(state, 'get', return_value=None)
	mocker.patch.object(open_weather_map, 'get_current_conditions', return_value=OWM_CURRENT)
	result = commands.cmd_temp(None)

	assert result.success is True
	assert result.has_data is True
	assert result.message == "☔ Damp and chilly, it's currently 12°C (54°F). Grab a waterproof coat."


def test_pressure_uses_owm_when_sensor_down(mocker):
	mocker.patch.object(state, 'get', return_value=None)
	mocker.patch.object(state, 'get_earliest', return_value=None)
	mocker.patch.object(open_weather_map, 'get_current_conditions', return_value=OWM_CURRENT)
	result = commands.cmd_pressure(None)

	assert result.success is True
	assert result.has_data is True
	assert result.message == 'Pressure is 1005.4hPa'


def test_humidity_owm_int_formats_without_trailing_zero(mocker):
	# OWM returns humidity as an int; '%%s' % round(int, 1) keeps it an int,
	# so the command renders '81%' (not '81.0%').
	mocker.patch.object(state, 'get', return_value=None)
	mocker.patch.object(open_weather_map, 'get_current_conditions', return_value=OWM_CURRENT)
	result = commands.cmd_humidity(None)

	assert result.success is True
	assert result.has_data is True
	assert result.message == 'Current humidity here is 81%'


def test_all_no_data_when_sensors_and_owm_down(mocker):
	mocker.patch.object(state, 'get', return_value=None)
	mocker.patch.object(open_weather_map, 'get_current_conditions', return_value=None)
	result = commands.cmd_all_sensors(None)

	assert result.success is True
	assert result.has_data is False
	assert result.message == 'Sorry, but no sensor data is available'


def test_temp_no_data_when_sensor_and_owm_down(mocker):
	mocker.patch.object(state, 'get', return_value=None)
	mocker.patch.object(open_weather_map, 'get_current_conditions', return_value=None)
	result = commands.cmd_temp(None)

	assert result.success is False
	assert result.has_data is False
	assert result.message == 'Sorry, but no temperature is available right now.'


# --- wind (OpenWeatherMap-only) ---------------------------------------------
#
# There is no local wind sensor, so the wind getters read the OWM current
# conditions cache directly (no state lookup), and the direction is shown as
# a 16-point compass shorthand.

WIND_CURRENT = {
	'temp': 12.0,
	'feels_like': 10.0,
	'pressure': 1005.4,
	'humidity': 81,
	'dt': 1794517200,
	'wind_speed': 4.5,
	'wind_deg': 320,
	'wind_gust': 9.0,
}


def test_wind_compass_cardinal_points(mocker):
	for deg, expected in [(0, 'N'), (90, 'E'), (180, 'S'), (270, 'W')]:
		mocker.patch.object(
			open_weather_map,
			'get_current_conditions',
			return_value={'wind_deg': deg},
		)
		assert get_wind_compass() == expected


def test_wind_compass_intercardinal_points(mocker):
	for deg, expected in [
		(11.25, 'NNE'),
		(67.5, 'ENE'),
		(157.5, 'SSE'),
		(247.5, 'WSW'),
		(337.5, 'NNW'),
	]:
		mocker.patch.object(
			open_weather_map,
			'get_current_conditions',
			return_value={'wind_deg': deg},
		)
		assert get_wind_compass() == expected


def test_wind_compass_none_without_deg(mocker):
	mocker.patch.object(
		open_weather_map,
		'get_current_conditions',
		return_value={'wind_speed': 4.5},
	)
	assert get_wind_compass() is None


def test_wind_compass_none_when_no_conditions(mocker):
	mocker.patch.object(open_weather_map, 'get_current_conditions', return_value=None)
	assert get_wind_compass() is None


def test_get_wind_speed_reads_owm(mocker):
	owm = mocker.patch.object(open_weather_map, 'get_current_conditions', return_value=WIND_CURRENT)
	assert get_wind_speed() == 4.5
	owm.assert_called_once()


def test_get_wind_gust_reads_owm(mocker):
	mocker.patch.object(open_weather_map, 'get_current_conditions', return_value=WIND_CURRENT)
	assert get_wind_gust() == 9.0


def test_wind_getters_none_when_no_conditions(mocker):
	mocker.patch.object(open_weather_map, 'get_current_conditions', return_value=None)
	assert get_wind_speed() is None
	assert get_wind_gust() is None


def _patch_wind_cmd(mocker, speed, gust, compass):
	mocker.patch.object(wind_command_module, 'get_wind_speed', return_value=speed)
	mocker.patch.object(wind_command_module, 'get_wind_gust', return_value=gust)
	mocker.patch.object(wind_command_module, 'get_wind_compass', return_value=compass)
	return commands.cmd_wind(None)


def test_wind_command_all_available(mocker):
	result = _patch_wind_cmd(mocker, 4.5, 9.0, 'NNW')
	assert result.success is True
	assert result.has_data is True
	assert result.message == 'Current wind here is 4.5 m/s NNW (gust 9.0 m/s)'


def test_wind_command_speed_only(mocker):
	result = _patch_wind_cmd(mocker, 4.5, None, None)
	assert result.success is True
	assert result.has_data is True
	assert result.message == 'Current wind here is 4.5 m/s'


def test_wind_command_missing_speed(mocker):
	result = _patch_wind_cmd(mocker, None, None, None)
	assert result.success is True
	assert result.has_data is False
	assert result.message == 'Sorry, but no wind available'


def test_all_owm_with_wind_shows_wind(mocker):
	owm = {
		'temp': 12.0,
		'feels_like': 10.0,
		'pressure': 1005.4,
		'humidity': 81,
		'dt': 1794517200,
		'wind_speed': 4.5,
		'wind_deg': 0,
		'wind_gust': 9.0,
	}
	mocker.patch.object(state, 'get', return_value=None)
	mocker.patch.object(state, 'get_earliest', return_value=None)
	mocker.patch.object(open_weather_map, 'get_current_conditions', return_value=owm)
	location = mocker.patch.object(all_sensors, 'config')
	location.location.label = 'cbus'
	result = commands.cmd_all_sensors(None)

	assert result.success is True
	assert result.message == (
		'☀ Weather in cbus:\n'
		'12.0°C (54°F) | 81.0% humidity | 1005.4 hPa | wind 4 m/s N'
	)


# --- sun --------------------------------------------------------
#
# Sunrise and sunset are service-only (no local sensor).  The command shows
# both events, each with a relative label against the (patched) clock.


def _patch_sun_cmd(mocker, sunrise, sunset, label='cbus'):
	"""
	Invoke cmd_sun with a mocked clock (9:00 PM) and patched sun getters.
	"""
	mocker.patch('time.time', return_value=1794517200)
	class _FakeDatetime(datetime):
		@classmethod
		def fromtimestamp(cls, ts, *args, **kwargs):
			return datetime.fromtimestamp(ts, tz=timezone.utc)
	mocker.patch.object(sun_lib, 'datetime', _FakeDatetime)
	mocker.patch.object(sun_lib, 'get_sunrise', return_value=sunrise)
	mocker.patch.object(sun_lib, 'get_sunset', return_value=sunset)
	location = mocker.patch.object(sun_command_module, 'config')
	location.location.label = label
	return sun_command_module.cmd_sun(None)


def test_sun_command_shows_both(mocker):
	result = _patch_sun_cmd(mocker, _SUNRISE, _SUNSET)

	assert result.success is True
	assert result.has_data is True
	assert result.message == (
		'Sun in cbus:\n'
		'Sunrise 12:13 PM (8h 46m ago)\n'
		'Sunset 10:18 PM (in 1h 19m)'
	)


def test_sun_command_only_sunset(mocker):
	result = _patch_sun_cmd(mocker, None, _SUNSET)

	assert result.success is True
	assert result.has_data is True
	assert result.message == (
		'Sun in cbus:\n'
		'Sunset 10:18 PM (in 1h 19m)'
	)


def test_sun_command_only_sunrise(mocker):
	result = _patch_sun_cmd(mocker, _SUNRISE, None)

	assert result.success is True
	assert result.has_data is True
	assert result.message == (
		'Sun in cbus:\n'
		'Sunrise 12:13 PM (8h 46m ago)'
	)


def test_sun_command_no_data(mocker):
	result = _patch_sun_cmd(mocker, None, None)

	assert result.success is True
	assert result.has_data is False
	assert result.message == 'Sorry, but no sunrise/sunset available'


def test_sun_command_missing_label(mocker):
	result = _patch_sun_cmd(mocker, _SUNRISE, _SUNSET, label='')

	assert result.success is True
	assert result.has_data is True
	assert result.message == (
		'Sun here:\n'
		'Sunrise 12:13 PM (8h 46m ago)\n'
		'Sunset 10:18 PM (in 1h 19m)'
	)
