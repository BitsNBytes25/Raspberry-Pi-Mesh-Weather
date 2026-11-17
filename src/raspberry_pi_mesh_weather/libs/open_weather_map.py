import requests
import logging
import time
from datetime import datetime
from .config import config
from .icon_map import get_weather_icon


# Reuse window for the in-memory current-conditions cache (seconds).
_DEFAULT_CURRENT_CACHE_SECONDS = 300
_UNSET = object()


class OpenWeatherMap:
	"""
	Client for the OpenWeatherMap API, providing lookups for the configured location.
	"""
	def __init__(self):
		"""
		Initializes the OpenWeatherMap client.
		"""
		self.api_key = config.weather.openweather_api_key
		self.lat = config.location.lat
		self.lon = config.location.lon
		self.base_url = "http://api.openweathermap.org/data"

		if not self.api_key:
			raise ValueError("OpenWeatherMap API Key not found. Please set OPENWEATHERMAP_API_KEY in your environment.")
		if not self.lat and not self.lon:
			raise ValueError("Latitude and Longitude not provided. Please set OPENWEATHERMAP_LOCATION or provide lat and lon.")

		# In-memory cache for get_current_conditions().  _UNSET means the cache is
		# empty (no fetch performed yet).
		self._current_cache = _UNSET
		self._current_cache_time = 0

	def _fetch_data(self, call: str, params: dict) -> dict:
		"""
		Fetches raw data from the OpenWeatherMap API for the given call.

		:return: the parsed JSON body, or {} on any request failure.
		"""

		try:
			response = requests.get(self.base_url + call, params=params, timeout=5)
			response.raise_for_status()  # Raises an HTTPError for bad responses (4xx or 5xx)
			return response.json()
		except requests.exceptions.RequestException as e:
			logging.error(f"Error fetching weather data from OpenWeatherMap: {e}")
			return {}

	def get_current_conditions(self) -> dict | None:
		"""
		Fetches the current weather conditions for the configured location and
		normalizes them into a single dict.

		The result is cached in memory for _DEFAULT_CURRENT_CACHE_SECONDS so that
		repeated reads (e.g. from the temperature/pressure/humidity getters when
		the local sensor is down) do not re-query the service.  A failed fetch is
		cached as None so a downed network is not re-pounded within the window.

		:return: a dict with keys temp, feels_like, pressure, humidity, dt, the
			wind block (wind_speed, wind_deg, wind_gust) and the sun events
			(sunrise, sunset, epoch seconds in the location's local time), or
			None if no data could be obtained.
		"""
		now = time.time()
		if (self._current_cache is not _UNSET
				and now - self._current_cache_time < _DEFAULT_CURRENT_CACHE_SECONDS):
			return self._current_cache

		data = self._fetch_data(
			'/2.5/weather',
			{
				'lat': self.lat,
				'lon': self.lon,
				'appid': self.api_key,
				'units': 'metric',  # temperature in Celsius (matches the local sensor)
			}
		)

		conditions = None
		if isinstance(data, dict) and isinstance(data.get('main'), dict):
			wind = data.get('wind') or {}
			sun = data.get('sys') or {}
			conditions = {
				'temp': data['main'].get('temp'),
				'feels_like': data['main'].get('feels_like'),
				# sea_level (hPa) matches the BME280's mean sea level pressure reading.
				'pressure': data['main'].get('sea_level'),
				'humidity': data['main'].get('humidity'),
				'dt': data.get('dt'),
				# wind block (metric: speed/gust in m/s, deg is the direction the
				# wind is blowing from)
				'wind_speed': wind.get('speed'),
				'wind_deg': wind.get('deg'),
				'wind_gust': wind.get('gust'),
				# sun events (epoch seconds, local time for the location).
				'sunrise': sun.get('sunrise'),
				'sunset': sun.get('sunset'),
			}

		self._current_cache = conditions
		self._current_cache_time = now
		return conditions

	def get_daily_forecast(self, count: int = 8) -> list[dict]:
		"""
		Fetches the next `count` forecast entries (a rolling window starting from
		now) and returns them normalized in chronological order, regardless of the
		time of day.

		This always returns the *next* periods, so calling it in the evening
		yields the current evening and spills into tomorrow, while calling it in
		the morning yields the morning, afternoon and evening of the current day.

		Each entry is a dict with the keys: dt, hour, date, temp, feels_like,
		humidity, pop, description and icon.

		:return: the list of normalized entries, or [] on fetch/parse failure.
		"""
		data = self._fetch_data(
			'/2.5/forecast',
			{
				'lat': self.lat,
				'lon': self.lon,
				'appid': self.api_key,
				'units': 'metric',  # Get temperature in Celsius
				'cnt': count,  # Limit to the next `count` (3-hourly) periods.
			}
		)

		if not data or 'list' not in data or not data['list']:
			logging.error("Error: No forecast data found in the response.")
			return []

		breakdown = []
		# The API already returns the next periods in order; sort defensively so the
		# result is always chronological.
		for item in sorted(data['list'], key=lambda entry: entry['dt']):
			local = datetime.fromtimestamp(item['dt'])
			breakdown.append({
				'dt': item['dt'],
				'hour': local.hour,
				'date': local.strftime('%Y-%m-%d'),
				'temp': item['main']['temp'],
				'feels_like': item['main']['feels_like'],
				'humidity': item['main']['humidity'],
				'pop': item['pop'],
				'description': item['weather'][0]['description'],
				'icon': get_weather_icon(item['weather'][0]['icon']),
			})

		return breakdown


# --- Module-level shared accessor ---------------------------------------------
#
# One process-wide client so that all the sensor getters (temperature, pressure,
# humidity) share a single in-memory cache.  This means a command that reads all
# three (e.g. the `all` command) triggers at most one OpenWeatherMap lookup
# rather than three.

_client = None


def _get_client():
	"""
	Lazily build and return the shared OpenWeatherMap client.

	:return: the shared client, or None if it could not be constructed (e.g. no
	API key or no location configured).
	"""
	global _client
	if _client is None:
		try:
			_client = OpenWeatherMap()
		except ValueError:
			logging.debug("OpenWeatherMap client unavailable; current-conditions fallback disabled")
			return None
	return _client


def get_current_conditions() -> dict | None:
	"""
	Shared in-memory cached accessor for the current-conditions lookup used as a
	fallback when local sensors are unavailable.

	:return: a normalized current-conditions dict, or None if unavailable.
	"""
	client = _get_client()
	if client is None:
		return None
	return client.get_current_conditions()
