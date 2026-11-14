import pytest
import requests

from datetime import datetime, timezone

from raspberry_pi_mesh_weather.libs import icon_map, open_weather_map
from raspberry_pi_mesh_weather.libs.open_weather_map import OpenWeatherMap


# The code computes hour/date from datetime.fromtimestamp; pin it to UTC so the
# "hour" and "date" values are deterministic and independent of the machine's
# timezone.
_UTC = timezone.utc


def _patch_time(mocker):
	"""
	Pin the datetime class used by the open_weather_map module to UTC.
	"""

	class _FakeDatetime(datetime):

		@classmethod
		def fromtimestamp(cls, ts, *args, **kwargs):
			return datetime.fromtimestamp(ts, tz=_UTC)

	mocker.patch.object(open_weather_map, 'datetime', _FakeDatetime)


def _patch_request(mocker, payload, status_code=200):
	"""
	Return a mock of requests.get that answers with a Response for `payload`.
	"""
	response = requests.Response()
	response.status_code = status_code
	response.json = lambda: payload
	return mocker.patch.object(open_weather_map.requests, 'get', return_value=response)


def _patch_request_failure(mocker):
	return mocker.patch.object(open_weather_map.requests, 'get',
								side_effect=requests.exceptions.ConnectionError('no connectivity'))


def _build_forecast(mocker, api_key='test-api-key', lat=39.96, lon=-83.0,
					icon_style='modern'):
	patched_config = mocker.patch.object(open_weather_map, 'config')
	patched_config.weather.openweather_api_key = api_key
	patched_config.location.lat = lat
	patched_config.location.lon = lon
	# Icon resolution reads the global config singleton (used by icon_map),
	# which is a different object from the module-local mock above.
	mocker.patch.object(icon_map.config.general, 'icon_style', icon_style)
	return OpenWeatherMap()


@pytest.fixture
def forecast(mocker):
	return _build_forecast(mocker)


# --- init -------------------------------------------------------------


def test_init_uses_config_values(forecast):
	assert forecast.api_key == 'test-api-key'
	assert forecast.lat == 39.96
	assert forecast.lon == -83.0
	assert forecast.base_url == 'http://api.openweathermap.org/data'


def test_init_requires_api_key(mocker):
	with pytest.raises(ValueError, match='OpenWeatherMap API Key not found'):
		_build_forecast(mocker, api_key='')


def test_init_requires_location(mocker):
	with pytest.raises(ValueError, match='Latitude and Longitude not provided'):
		_build_forecast(mocker, lat=None, lon=None)


def test_init_accepts_a_single_coordinate(mocker):
	# The check is `not lat and not lon` — one coordinate is sufficient.
	forecast = _build_forecast(mocker, lat=39.96, lon=None)
	assert forecast.lat == 39.96
	assert forecast.lon is None


# --- _fetch_data -------------------------------------------------------


def test_fetch_data_returns_parsed_json(forecast, mocker):
	mock_get = _patch_request(mocker, {'cod': '200'})
	assert forecast._fetch_data('/2.5/forecast', {'a': 1}) == {'cod': '200'}
	mock_get.assert_called_once_with(
		'http://api.openweathermap.org/data/2.5/forecast',
		params={'a': 1},
		timeout=5,
	)


def test_fetch_data_returns_empty_on_request_exception(forecast, mocker):
	_patch_request_failure(mocker)
	assert forecast._fetch_data('/2.5/forecast', {'a': 1}) == {}


def test_fetch_data_returns_empty_on_http_error(forecast, mocker):
	_patch_request(mocker, {'cod': '401'}, status_code=401)
	assert forecast._fetch_data('/2.5/forecast', {'a': 1}) == {}


# --- get_daily_forecast ------------------------------------------------


def test_get_daily_forecast_returns_next_entries_in_the_evening(columbus_afternoon,
																forecast, mocker):
	_patch_time(mocker)
	_patch_request(mocker, columbus_afternoon)
	result = forecast.get_daily_forecast()

	assert len(result) == 8
	# chronological by dt
	assert [e['dt'] for e in result] == sorted([e['dt'] for e in result])
	# the rolling window (UTC hours) starts on the evening and spills into the next day
	assert [e['hour'] for e in result] == [21, 0, 3, 6, 9, 12, 15, 18]
	assert result[0]['date'] != result[1]['date']
	assert result[0]['description'] == 'light rain'
	assert result[0]['icon'] == chr(0x1F326) + chr(0xFE0F)  # 🌦️
	assert result[0]['temp'] == 9.54
	assert result[0]['feels_like'] == 7.2
	assert result[0]['humidity'] == 81
	assert result[0]['pop'] == 1

	# every entry exposes the normalized fields
	assert set(result[0].keys()) == {
		'dt', 'hour', 'date', 'temp', 'feels_like', 'humidity', 'pop',
		'description', 'icon',
	}


def test_get_daily_forecast_returns_next_entries_in_the_morning(columbus_morning,
																forecast, mocker):
	_patch_time(mocker)
	_patch_request(mocker, columbus_morning)
	result = forecast.get_daily_forecast()

	assert len(result) == 8
	# the rolling window (UTC hours) starts in the morning and spans today + next day
	assert [e['hour'] for e in result] == [9, 12, 15, 18, 21, 0, 3, 6]
	assert result[0]['hour'] == 9
	assert result[0]['description'] == 'light rain'
	assert result[0]['icon'] == chr(0x1F326) + chr(0xFE0F)  # 🌦️
	assert len({e['date'] for e in result}) == 2


def test_get_daily_forecast_returns_empty_on_request_failure(forecast, mocker):
	_patch_request_failure(mocker)
	assert forecast.get_daily_forecast() == []


def test_get_daily_forecast_returns_empty_on_malformed_response(forecast, mocker):
	_patch_request(mocker, {'cod': '401'})
	assert forecast.get_daily_forecast() == []


def test_get_daily_forecast_returns_empty_on_empty_list(forecast, mocker):
	_patch_request(mocker, {'cod': '200', 'list': []})
	assert forecast.get_daily_forecast() == []


def test_get_daily_forecast_respects_compatible_icon_style(columbus_afternoon, mocker):
	_patch_time(mocker)
	_patch_request(mocker, columbus_afternoon)
	client = _build_forecast(mocker, icon_style='compatible')
	result = client.get_daily_forecast()
	# 10d (light rain) maps to the umbrella-with-rain-drops glyph in the
	# widely-supported set instead of the colour emoji.
	assert result[0]['icon'] == '\u2614'


# --- get_current_conditions ---------------------------------------------------


@pytest.fixture
def reset_shared_client():
	"""
	Isolate the process-wide shared client between tests that use the
	module-level get_current_conditions() accessor.
	"""
	open_weather_map._client = None
	yield
	open_weather_map._client = None


def test_get_current_conditions_normalizes(columbus_current, forecast, mocker):
	_patch_request(mocker, columbus_current)
	result = forecast.get_current_conditions()

	assert result == {
		'temp': 12.0,
		'feels_like': 10.0,
		'pressure': 1005.4,
		'humidity': 81,
		'dt': 1794517200,
	}


def test_get_current_conditions_cached_within_ttl(columbus_current, forecast, mocker):
	_patch_request(mocker, columbus_current)
	first = forecast.get_current_conditions()
	second = forecast.get_current_conditions()

	assert first == second
	# The second read is served from the in-memory cache, not the service.
	assert open_weather_map.requests.get.call_count == 1


def test_get_current_conditions_caches_failure(columbus_current, forecast, mocker):
	_patch_request_failure(mocker)
	assert forecast.get_current_conditions() is None
	assert forecast.get_current_conditions() is None
	# A failed fetch is cached too, so a downed network is not re-pounded.
	assert open_weather_map.requests.get.call_count == 1


def test_get_current_conditions_none_on_malformed(forecast, mocker):
	_patch_request(mocker, {'cod': '401'})
	assert forecast.get_current_conditions() is None


def test_get_current_conditions_none_on_missing_main(forecast, mocker):
	_patch_request(mocker, {})
	assert forecast.get_current_conditions() is None


# --- module-level shared accessor -------------------------------------------


def test_module_accessor_normalizes(columbus_current, reset_shared_client, mocker):
	_build_forecast(mocker)  # patch open_weather_map.config for the shared client
	_patch_request(mocker, columbus_current)
	result = open_weather_map.get_current_conditions()

	assert result == {
		'temp': 12.0,
		'feels_like': 10.0,
		'pressure': 1005.4,
		'humidity': 81,
		'dt': 1794517200,
	}
	assert open_weather_map.requests.get.call_count == 1


def test_module_accessor_cached_within_ttl(columbus_current, reset_shared_client, mocker):
	_build_forecast(mocker)
	_patch_request(mocker, columbus_current)
	first = open_weather_map.get_current_conditions()
	second = open_weather_map.get_current_conditions()

	assert first == second
	# Single shared client, single cache, one service call.
	assert open_weather_map.requests.get.call_count == 1


def test_module_accessor_none_without_api_key(columbus_current, reset_shared_client, mocker):
	_patch_request(mocker, columbus_current)
	config = mocker.patch.object(open_weather_map, 'config')
	config.weather.openweather_api_key = ''
	config.location.lat = 39.96
	config.location.lon = -83.0

	# OpenWeatherMap() raises with no key, so the shared client is never built.
	assert open_weather_map.get_current_conditions() is None
	assert open_weather_map._client is None
