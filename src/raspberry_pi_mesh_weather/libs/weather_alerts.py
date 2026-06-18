import requests
import logging
from datetime import datetime


def parse_alert_emojis(event_name):
	"""
    Parses an NWS event string, determines if it is a Watch or a Warning,
    and appends a color block indicator along with time-remaining logic.
    """
	NWS_EVENT_EMOJIS = {
		"tornado": "🌪️",
		"thunderstorm": "⛈️",
		"flash flood": "🌊",
		"flood": "🌊",
		"tsunami": "🌊",
		"hurricane": "🌀",
		"typhoon": "🌀",
		"tropical storm": "🌀",
		"blizzard": "❄️",
		"winter storm": "❄️",
		"ice storm": "❄️",
		"snow": "❄️",
		"freeze": "🥶",
		"frost": "🥶",
		"wind chill": "🥶",
		"heat": "🥵",
		"wind": "💨",
		"gale": "💨",
		"dust": "🏜️",
		"sand": "🏜️",
		"fog": "🌫️",
		"dense smoke": "🌫️",
		"air quality": "😷",
		"fire": "🔥",
		"red flag": "🔥",
		"avalanche": "🏔️",
		"rip current": "🏖️",
		"surf": "🏖️",
		"marine": "🚢",
		"special weather statement": "ℹ️"
	}

	event_clean = event_name.lower()

	for keyword, emoji in NWS_EVENT_EMOJIS.items():
		if keyword in event_clean:
			return emoji

	return "⚠️"  # default


def get_alerts(latitude, longitude):
	url = f"https://api.weather.gov/alerts/active?point={latitude},{longitude}"
	try:
		response = requests.get(
			url,
			headers = {
				"User-Agent": "RaspberryPiMeshWeather (https://github.com/BitsNBytes25/Raspberry-Pi-Mesh-Weather)"
			}
		)
		response.raise_for_status()  # Raises an HTTPError for bad responses (4xx or 5xx)
		data = response.json()
		features = data.get("features", [])
		if not features:
			# Nothing going on, good!
			return []

		ret = []
		# Loop through the list of active alerts
		for alert in features:
			props = alert.get("properties", {})

			# Extract clean, normalized NWS properties
			expires = datetime.fromisoformat(props.get('expires'))
			event = props.get("event", "Unknown Alert")
			icon = parse_alert_emojis(event)
			ends = expires.strftime("%I:%M %p")
			ret.append(f"{icon}  {event} until {ends}")

		return ret

	except requests.exceptions.RequestException as e:
		logging.error(f"Error fetching weather data from api.weather.gov: {e}")
		return {}
