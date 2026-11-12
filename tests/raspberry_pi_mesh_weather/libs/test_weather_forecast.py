from datetime import date, datetime, timezone

import pytest
import requests

from raspberry_pi_mesh_weather.libs import weather_forecast
from raspberry_pi_mesh_weather.libs.weather_forecast import WeatherForecast


# All fixture timestamps fall on this UTC date; the fixture's dt_txt fields are
# in UTC, so pin the "hour" used for the morning/noon/afternoon windows to UTC
# so the tests are independent of the machine's timezone.
FAKE_TODAY = date(2026, 11, 13)
_UTC = timezone.utc


def _patch_time(mocker, today, entry_date=None):
	"""
	Pin the date classes used by the weather_forecast module.

	:param today: value returned by date.today()
	:param entry_date: value returned by date.fromtimestamp; every entry counts as
	"today" if not provided.
	"""

	class _FakeDate(date):

		@classmethod
		def fromtimestamp(cls, ts, *args, **kwargs):
			return entry_date or today

		@classmethod
		def today(cls):
			return today

	class _FakeDatetime(datetime):

		@classmethod
		def fromtimestamp(cls, ts, *args, **kwargs):
			return datetime.fromtimestamp(ts, tz=_UTC)

	mocker.patch.object(weather_forecast, 'date', _FakeDate)
	mocker.patch.object(weather_forecast, 'datetime', _FakeDatetime)


def _patch_request(mocker, payload, status_code=200):
	"""
	Return a mock of requests.get that answers with a Response for `payload`.
	"""
	response = requests.Response()
	response.status_code = status_code
	response.json = lambda: payload
	return mocker.patch.object(weather_forecast.requests, 'get', return_value=response)


def _patch_request_failure(mocker):
	return mocker.patch.object(weather_forecast.requests, 'get',
								side_effect=requests.exceptions.ConnectionError('no connectivity'))


def _build_forecast(mocker, api_key='test-api-key', lat=39.96, lon=-83.0):
	patched_config = mocker.patch.object(weather_forecast, 'config')
	patched_config.weather.openweather_api_key = api_key
	patched_config.location.lat = lat
	patched_config.location.lon = lon
	return WeatherForecast()


@pytest.fixture
def forecast(mocker):
	return _build_forecast(mocker)


@pytest.fixture
def fixed_time(mocker):
	_patch_time(mocker, today=FAKE_TODAY)


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
	)


def test_fetch_data_returns_empty_on_request_exception(forecast, mocker):
	_patch_request_failure(mocker)
	assert forecast._fetch_data('/2.5/forecast', {'a': 1}) == {}


def test_fetch_data_returns_empty_on_http_error(forecast, mocker):
	_patch_request(mocker, {'cod': '401'}, status_code=401)
	assert forecast._fetch_data('/2.5/forecast', {'a': 1}) == {}


# --- get_daily_forecast ------------------------------------------------


def test_get_daily_forecast_returns_summary(columbus_afternoon, fixed_time,
											forecast, mocker):
	_patch_request(mocker, columbus_afternoon)
	result = forecast.get_daily_forecast()
	assert result['date'] == '2026-11-13'
	assert result['high_temp'] == 10
	assert result['low_temp'] == 4
	assert result['avg_humidity'] == 85
	assert result['general_outlook'] == (
		'🌧️  early light rain\n'
		'☁️  noon broken clouds\n'
		'🌦️  late light rain'
	)


def test_get_daily_forecast_falls_back_to_first_entry(columbus_afternoon,
														forecast, mocker):
	_patch_time(mocker, today=FAKE_TODAY, entry_date=date(2026, 1, 1))
	_patch_request(mocker, columbus_afternoon)
	result = forecast.get_daily_forecast()
	assert result['date'] == '2026-11-13'
	assert result['high_temp'] == 10
	assert result['low_temp'] == 10
	assert result['avg_humidity'] == 81
	assert result['general_outlook'] == ''


def test_get_daily_forecast_returns_empty_on_request_failure(forecast, mocker):
	_patch_request_failure(mocker)
	assert forecast.get_daily_forecast() == {}


def test_get_daily_forecast_returns_empty_on_malformed_response(forecast, mocker):
	_patch_request(mocker, {'cod': '401'})
	assert forecast.get_daily_forecast() == {}


# --- get_description ---------------------------------------------------


def test_get_description_same_all_day(forecast):
	breakdown = [
		{'hour': 8, 'icon': '☀️', 'description': 'clear sky'},
		{'hour': 12, 'icon': '☀️', 'description': 'clear sky'},
		{'hour': 16, 'icon': '☀️', 'description': 'clear sky'},
	]
	assert forecast.get_description(breakdown) == '☀️  clear sky all day'


def test_get_description_same_morning_and_noon(forecast):
	breakdown = [
		{'hour': 8, 'icon': '☀️', 'description': 'clear sky'},
		{'hour': 12, 'icon': '☀️', 'description': 'clear sky'},
		{'hour': 16, 'icon': '🌧️', 'description': 'light rain'},
	]
	assert forecast.get_description(breakdown) == (
		'☀️  clear sky\nuntil afternoon then\n🌧️  light rain'
	)


def test_get_description_same_noon_and_afternoon(forecast):
	breakdown = [
		{'hour': 8, 'icon': '🌧️', 'description': 'light rain'},
		{'hour': 12, 'icon': '☁️', 'description': 'broken clouds'},
		{'hour': 16, 'icon': '☁️', 'description': 'broken clouds'},
	]
	assert forecast.get_description(breakdown) == (
		'🌧️  light rain\nthen around noon\n☁️  broken clouds'
	)


def test_get_description_all_different(forecast):
	breakdown = [
		{'hour': 8, 'icon': '☀️', 'description': 'clear sky'},
		{'hour': 12, 'icon': '☁️', 'description': 'broken clouds'},
		{'hour': 16, 'icon': '🌧️', 'description': 'light rain'},
	]
	assert forecast.get_description(breakdown) == (
		'☀️  early clear sky\n'
		'☁️  noon broken clouds\n'
		'🌧️  late light rain'
	)


def test_get_description_missing_periods(forecast):
	breakdown = [
		{'hour': 8, 'icon': '☀️', 'description': 'clear sky'},
		{'hour': 16, 'icon': '🌧️', 'description': 'light rain'},
	]
	assert forecast.get_description(breakdown) == (
		'☀️  early clear sky\n🌧️  late light rain'
	)


def test_get_description_no_matching_periods(forecast):
	assert forecast.get_description([
		{'hour': 2, 'icon': '🌙', 'description': 'clear night'},
	]) == ''


def test_get_description_window_boundaries(forecast):
	# Morning: 7 <= h < 11; noon: 11 <= h < 13; afternoon: 15 <= h < 19.
	breakdown = [
		{'hour': 7, 'icon': '☀️', 'description': 'clear sky'},
		{'hour': 11, 'icon': '🌧️', 'description': 'light rain'},
		{'hour': 15, 'icon': '⛈️', 'description': 'thunderstorms'},
	]
	assert forecast.get_description(breakdown) == (
		'☀️  early clear sky\n'
		'🌧️  noon light rain\n'
		'⛈️  late thunderstorms'
	)


def test_get_description_last_match_wins_in_window(forecast):
	breakdown = [
		{'hour': 8, 'icon': '☀️', 'description': 'clear sky'},
		{'hour': 10, 'icon': '🌧️', 'description': 'light rain'},
		{'hour': 12, 'icon': '☁️', 'description': 'broken clouds'},
		{'hour': 12, 'icon': '☁️', 'description': 'overcast clouds'},
		{'hour': 16, 'icon': '⛅', 'description': 'few clouds'},
	]
	assert forecast.get_description(breakdown) == (
		'🌧️  early light rain\n'
		'☁️  noon overcast clouds\n'
		'⛅  late few clouds'
	)
