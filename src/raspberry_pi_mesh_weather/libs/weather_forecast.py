import requests
import os
from datetime import date, datetime


class WeatherForecast:
    """
    Handles fetching daily weather forecast data from an external API.
    Assumes OPENWEATHERMAP_API_KEY is set in the environment variables.
    """
    def __init__(self, api_key: str = None):
        """
        Initializes the WeatherForecast client.

        Args:
            api_key: The OpenWeatherMap API key. If None, it attempts to load it from the environment.
        """
        self.api_key = api_key if api_key else os.getenv("OPENWEATHERMAP_API_KEY")
        if not self.api_key:
            raise ValueError("OpenWeatherMap API Key not found. Please set OPENWEATHERMAP_API_KEY in your environment.")
        
        self.base_url = "http://api.openweathermap.org/data/2.5/forecast"

    def _fetch_data(self, city: str) -> dict:
        """
        Fetches raw forecast data from OpenWeatherMap for a given city.
        """
        params = {
            'q': city,
            'appid': self.api_key,
            'units': 'metric'  # Get temperature in Celsius
        }
        try:
            response = requests.get(self.base_url, params=params)
            response.raise_for_status()  # Raises an HTTPError for bad responses (4xx or 5xx)
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching weather data from OpenWeatherMap: {e}")
            return {}

    def get_description(self, breakdown) -> str:
        """
        Get a friendly description of an overview of the weather conditions throughout the day

        :param breakdown:
        :return:
        """

        morning = None
        morning_i = None
        noon = None
        noon_i = None
        afternoon = None
        afternoon_i = None
        for item in breakdown:
            if 7 <= item['hour'] < 11:
                morning_i = item['icon']
                morning = item['description']
            elif 11 <= item['hour'] < 13:
                noon_i = item['icon']
                noon = item['description']
            elif 15 <= item['hour'] < 19:
                afternoon_i = item['icon']
                afternoon = item['description']

        if morning and noon and afternoon:
            if morning == noon == afternoon:
                return f"{morning_i}  {morning} all day"
            if morning == noon:
                return f"{morning_i}  {morning}\nuntil afternoon then\n{afternoon_i}  {afternoon}"
            if noon == afternoon:
                return f"{morning_i}  {morning}\nthen around noon\n{afternoon_i}  {afternoon}"

        parts = []
        if morning:
            parts.append(f"{morning_i}  early {morning}")
        if noon:
            parts.append(f"{noon_i}  noon {noon}")
        if afternoon:
            parts.append(f"{afternoon_i}  late {afternoon}")

        return '\n'.join(parts)


    def get_daily_forecast(self, location: str = "London", lat: float = None, lon: float = None) -> dict:
        """
        Retrieves and processes the forecast for a single day (today).

        Args:
            location: The city name or postal code to fetch the weather for. Defaults to "London".
            lat: Latitude of the location (optional, overrides location_id if provided).
            lon: Longitude of the location (optional, overrides location_id if provided).

        Returns:
            A dictionary containing today's summarized forecast data, or an empty dict on failure.
        """
        if lat is not None and lon is not None:
            # Use coordinates if provided
            params = {'lat': lat, 'lon': lon, 'appid': self.api_key, 'units': 'metric'}
            response = requests.get(self.base_url, params=params)
            response.raise_for_status()
            data = response.json()
            city = f"Lat:{lat:.2f}, Lon:{lon:.2f}" # Set city name for output clarity
        else:
            # Use location ID (City Name or Postal Code)
            params = {'q': location, 'appid': self.api_key, 'units': 'metric'}
            response = requests.get(self.base_url, params=params)
            response.raise_for_status()
            data = response.json()
            city = location # Use the provided ID as city name

        if not data or 'list' not in data:
            return {}

        # Find the entry for today (or the first one if we assume the API returns today first)
        today_forecasts = [item for item in data['list'] if date.fromtimestamp(item['dt']) == date.today()]
        
        if not today_forecasts:
            # Fallback: If no exact match, take the very first entry as 'today's' forecast
            print("Warning: No exact daily match found for today. Using the first available forecast.")
            today_forecasts = [data['list'][0]]

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
        for item in today_forecasts:
            breakdown.append({
                'hour': datetime.fromtimestamp(item['dt']).hour,
                'temp': item['main']['temp'],
                'humidity': item['main']['humidity'],
                'pop': item['pop'],  # Probability of Precipitation
                'description': item['weather'][0]['description'],
                'icon': weather_emojis.get(item['weather'][0]['icon'], ''),
            })

        # pprint(breakdown)

        # Calculate metrics
        watches = data.get('alerts', [])
        high_temp = round(max(item['temp'] for item in breakdown))
        low_temp = round(min(item['temp'] for item in breakdown))
        avg_humidity = round(sum(item['humidity'] for item in breakdown) / len(breakdown))
        general_outlook = self.get_description(breakdown)

        # Compile the result
        return {
            "location": city,
            "date": date.today().strftime("%Y-%m-%d"),
            "high_temp": high_temp,
            "low_temp": low_temp,
            "avg_humidity": avg_humidity,
            "general_outlook": general_outlook,
            "watches": watches # List of alerts from the API
        }

# Example usage (for testing):
if __name__ == '__main__':
    try:
        # Attempt to get city name from environment if available, otherwise use default
        location_to_check = os.getenv("OPENWEATHERMAP_LOCATION", "London")
        print(f"--- Fetching weather forecast for {location_to_check} ---")
        weather_client = WeatherForecast()
        forecast = weather_client.get_daily_forecast(location=location_to_check)

        if forecast:
            print("\n✅ Daily Forecast Successfully Retrieved:")
            for key, value in forecast.items():
                print(f"  {key.replace('_', ' ').capitalize()}: {value}")
        else:
            print("\n❌ Failed to retrieve weather forecast.")

    except ValueError as ve:
        print(f"\n❌ Configuration Error: {ve}")
    except Exception as e:
        print(f"\n❌ An unexpected error occurred during execution: {e}")