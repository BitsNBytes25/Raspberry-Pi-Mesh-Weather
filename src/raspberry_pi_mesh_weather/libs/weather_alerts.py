import requests
import logging
from datetime import datetime

"""
All event types, as provided by /alerts/types:

"911 Telephone Outage",
"Administrative Message",
"Air Quality Alert",
"Air Stagnation Advisory",
"Ashfall Advisory",
"Ashfall Warning",
"Avalanche Advisory",
"Avalanche Warning",
"Avalanche Watch",
"Beach Hazards Statement",
"Blizzard Warning",
"Blowing Dust Advisory",
"Blowing Dust Warning",
"Blue Alert",
"Brisk Wind Advisory",
"Child Abduction Emergency",
"Civil Danger Warning",
"Civil Emergency Message",
"Coastal Flood Advisory",
"Coastal Flood Statement",
"Coastal Flood Warning",
"Coastal Flood Watch",
"Cold Weather Advisory",
"Dense Fog Advisory",
"Dense Smoke Advisory",
"Dust Advisory",
"Dust Storm Warning",
"Earthquake Warning",
"Evacuation Immediate",
"Extreme Heat Warning",
"Extreme Heat Watch",
"Extreme Cold Warning",
"Extreme Cold Watch",
"Extreme Fire Danger",
"Extreme Wind Warning",
"Fire Warning",
"Fire Weather Watch",
"Flash Flood Statement",
"Flash Flood Warning",
"Flash Flood Watch",
"Flood Advisory",
"Flood Statement",
"Flood Warning",
"Flood Watch",
"Freeze Warning",
"Freeze Watch",
"Freezing Fog Advisory",
"Freezing Spray Advisory",
"Frost Advisory",
"Gale Warning",
"Gale Watch",
"Hazardous Materials Warning",
"Hazardous Seas Warning",
"Hazardous Seas Watch",
"Hazardous Weather Outlook",
"Heat Advisory",
"Heavy Freezing Spray Warning",
"Heavy Freezing Spray Watch",
"High Surf Advisory",
"High Surf Warning",
"High Wind Warning",
"High Wind Watch",
"Hurricane Force Wind Warning",
"Hurricane Force Wind Watch",
"Hurricane Warning",
"Hurricane Watch",
"Hydrologic Outlook",
"Ice Storm Warning",
"Lake Effect Snow Warning",
"Lake Wind Advisory",
"Lakeshore Flood Advisory",
"Lakeshore Flood Statement",
"Lakeshore Flood Warning",
"Lakeshore Flood Watch",
"Law Enforcement Warning",
"Local Area Emergency",
"Low Water Advisory",
"Marine Weather Statement",
"Nuclear Power Plant Warning",
"Radiological Hazard Warning",
"Red Flag Warning",
"Rip Current Statement",
"Severe Thunderstorm Warning",
"Severe Thunderstorm Watch",
"Severe Weather Statement",
"Shelter In Place Warning",
"Short Term Forecast",
"Small Craft Advisory",
"Snow Squall Warning",
"Special Marine Warning",
"Special Weather Statement",
"Storm Surge Warning",
"Storm Surge Watch",
"Storm Warning",
"Storm Watch",
"Test",
"Tornado Warning",
"Tornado Watch",
"Tropical Cyclone Local Statement",
"Tropical Storm Warning",
"Tropical Storm Watch",
"Tsunami Advisory",
"Tsunami Warning",
"Tsunami Watch",
"Typhoon Warning",
"Typhoon Watch",
"Volcano Warning",
"Wind Advisory",
"Winter Storm Warning",
"Winter Storm Watch",
"Winter Weather Advisory"

All severities:
"Extreme",
"Severe",
"Moderate",
"Minor",
"Unknown"

All urgencies:
"Immediate",
"Expected",
"Future",
"Past",
"Unknown"

All Certainties:
"Observed",
"Likely",
"Possible",
"Unlikely",
"Unknown"
"""


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
			event = props.get('headline', props.get('event', 'Unknown Alert'))
			icon = parse_alert_emojis(props.get('event', 'Unknown Alert'))
			ends = expires.strftime("%I:%M %p")
			ret.append(f"{icon}  {event}")

		return ret

	except requests.exceptions.RequestException as e:
		logging.error(f"Error fetching weather data from api.weather.gov: {e}")
		return {}
