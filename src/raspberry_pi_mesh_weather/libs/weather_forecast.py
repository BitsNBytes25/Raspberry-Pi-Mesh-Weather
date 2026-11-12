import requests
import logging
from datetime import datetime
from .config import config


class WeatherForecast:
	"""
	Handles fetching daily weather forecast data from an external API.
	"""
	def __init__(self):
		"""
		Initializes the WeatherForecast client.
		"""
		self.api_key = config.weather.openweather_api_key
		self.lat = config.location.lat
		self.lon = config.location.lon
		self.base_url = "http://api.openweathermap.org/data"

		if not self.api_key:
			raise ValueError("OpenWeatherMap API Key not found. Please set OPENWEATHERMAP_API_KEY in your environment.")
		if not self.lat and not self.lon:
			raise ValueError("Latitude and Longitude not provided. Please set OPENWEATHERMAP_LOCATION or provide lat and lon.")

	def _fetch_data(self, call: str, params: dict) -> dict:
		"""
		Fetches raw forecast data from OpenWeatherMap for a given city.
		"""

		try:
			response = requests.get(self.base_url + call, params=params)
			response.raise_for_status()  # Raises an HTTPError for bad responses (4xx or 5xx)
			return response.json()
		except requests.exceptions.RequestException as e:
			logging.error(f"Error fetching weather data from OpenWeatherMap: {e}")
			return {}

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

		# Include pretty UTF-8 emoticons for the various weather codes provided by OpenWeatherMap
		weather_emojis = {
			"01d": "☀️", "01n": "🌙",
			"02d": "⛅", "02n": "☁️",
			"03d": "🌤️", "03n": "☁️",
			"04d": "☁️", "04n": "☁️",
			"09d": "🌧️", "09n": "🌧️",
			"10d": "🌦️", "10n": "🌧️",
			"11d": "⛈️", "11n": "⛈️",
			"13d": "❄️", "13n": "❄️",
			"50d": "🌫️", "50n": "🌫️"
		}

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
				'icon': weather_emojis.get(item['weather'][0]['icon'], ''),
			})

		return breakdown
