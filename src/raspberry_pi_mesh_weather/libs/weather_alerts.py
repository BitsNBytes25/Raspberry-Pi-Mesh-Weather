"""NWS active-alert client.

Fetches active alerts for a location and exposes:

* `get_alerts()`   - a list of tracked alerts, as records of
  {icon, title, id, expiration};
* `get_new_alerts()` - only the alerts not yet broadcast, tracking
  previously-broadcast ids in memory and pruning them when they expire.

Only alerts whose event, severity, urgency and certainty all fall within the
tracked sets (docs/weather_alert_keys.md) are considered; the rest are ignored.
"""
import logging
import requests
from datetime import datetime, timezone

from .icon_map import get_icon

#
# Tracked NWS alert values, from docs/weather_alert_keys.md.
#
# An alert is only broadcast when its event, severity, urgency and certainty
# all fall within the respective sets below; any alert failing a check is
# ignored.
#
TRACKED_EVENTS = {
	"ashfall warning",
	"avalanche warning",
	"blizzard warning",
	"blowing dust warning",
	"civil danger warning",
	"civil emergency message",
	"coastal flood warning",
	"dust storm warning",
	"earthquake warning",
	"evacuation immediate",
	"extreme heat warning",
	"extreme cold warning",
	"extreme fire danger",
	"extreme wind warning",
	"fire warning",
	"flash flood warning",
	"flood warning",
	"hazardous materials warning",
	"hazardous seas warning",
	"heavy freezing spray warning",
	"high surf warning",
	"high wind warning",
	"hurricane force wind warning",
	"hurricane warning",
	"ice storm warning",
	"lake effect snow warning",
	"lakeshore flood warning",
	"law enforcement warning",
	"local area emergency",
	"nuclear power plant warning",
	"radiological hazard warning",
	"red flag warning",
	"severe thunderstorm warning",
	"shelter in place warning",
	"snow squall warning",
	"special marine warning",
	"storm surge warning",
	"storm warning",
	"tornado warning",
	"tropical storm warning",
	"tsunami warning",
	"typhoon warning",
	"winter storm warning",
}

TRACKED_SEVERITIES = {
	"extreme",
	"severe",
}

TRACKED_URGENCIES = {
	"immediate",
	"expected",
}

TRACKED_CERTAINTIES = {
	"observed",
	"likely",
}

#
# Exact event name -> standard icon name, for the tracked events only.
# "warning" is the glyph used where an event has no natural counterpart.
#
EVENT_ICONS = {
	"ashfall warning": "warning",
	"avalanche warning": "avalanche",
	"blizzard warning": "snow",
	"blowing dust warning": "dust",
	"civil danger warning": "warning",
	"civil emergency message": "warning",
	"coastal flood warning": "flood",
	"dust storm warning": "dust",
	"earthquake warning": "warning",
	"evacuation immediate": "warning",
	"extreme heat warning": "heat",
	"extreme cold warning": "freezing",
	"extreme fire danger": "fire",
	"extreme wind warning": "wind",
	"fire warning": "fire",
	"flash flood warning": "flood",
	"flood warning": "flood",
	"hazardous materials warning": "warning",
	"hazardous seas warning": "ship",
	"heavy freezing spray warning": "freezing",
	"high surf warning": "surf",
	"high wind warning": "wind",
	"hurricane force wind warning": "cyclone",
	"hurricane warning": "cyclone",
	"ice storm warning": "snow",
	"lake effect snow warning": "snow",
	"lakeshore flood warning": "flood",
	"law enforcement warning": "warning",
	"local area emergency": "warning",
	"nuclear power plant warning": "warning",
	"radiological hazard warning": "warning",
	"red flag warning": "fire",
	"severe thunderstorm warning": "thunderstorm",
	"shelter in place warning": "warning",
	"snow squall warning": "snow",
	"special marine warning": "ship",
	"storm surge warning": "flood",
	"storm warning": "warning",
	"tornado warning": "cyclone",
	"tropical storm warning": "cyclone",
	"tsunami warning": "flood",
	"typhoon warning": "cyclone",
	"winter storm warning": "snow",
}

#
# In-memory record of alert ids already broadcast: alert id -> expiration.
# Expired entries are dropped on each call to keep memory bounded in the
# long-running process.
#
_BROADCAST_IDS: dict[str, datetime] = {}


def parse_alert_icon(event_name):
	"""
	Resolve a tracked NWS event name to the alert glyph to display.

	Exact match against the tracked events (EVENT_ICONS) so the glyph is
	resolved through the active `icon_style`; anything else falls back to the
	generic warning glyph.
	"""
	event_clean = (event_name or "").strip().lower()
	return get_icon(EVENT_ICONS.get(event_clean, "warning"))


def _is_tracked(props):
	"""
	Return True only when every tracked-value set is satisfied: event,
	severity, urgency and certainty all within their tracked values.
	"""
	event = (props.get('event', '')).strip().lower()
	if event not in TRACKED_EVENTS:
		return False
	if (props.get('severity', '')).strip().lower() not in TRACKED_SEVERITIES:
		return False
	if (props.get('urgency', '')).strip().lower() not in TRACKED_URGENCIES:
		return False
	return (props.get('certainty', '')).strip().lower() in TRACKED_CERTAINTIES


def _alert_dict(props):
	"""Build the broadcastable record for a single tracked alert."""
	return {
		"icon": parse_alert_icon(props.get("event", "")),
		"title": props.get("headline", props.get("event", "Unknown Alert")),
		"id": props.get("id", ""),
		"expiration": datetime.fromisoformat(props["expires"]),
	}


def get_alerts(latitude, longitude):
	"""
	Fetch the active alerts for a location and return a list of records,
	each {icon, title, id, expiration}, for the tracked alerts only.
	Non-tracked alerts are ignored.
	"""
	url = f"https://api.weather.gov/alerts/active?point={latitude},{longitude}"
	try:
		response = requests.get(
			url,
			headers={
				"User-Agent": "RaspberryPiMeshWeather (https://github.com/BitsNBytes25/Raspberry-Pi-Mesh-Weather)"
			}
		)
		response.raise_for_status()
		data = response.json()
		features = data.get("features", [])
		ret = []
		for alert in features:
			props = alert.get("properties", {})
			if _is_tracked(props):
				ret.append(_alert_dict(props))
		return ret
	except requests.exceptions.RequestException as e:
		logging.error(f"Error fetching weather data from api.weather.gov: {e}")
		return []


def get_new_alerts(latitude, longitude):
	"""
	Return only the alerts not already broadcast.

	Broadcast ids are held in memory (`_BROADCAST_IDS`) and pruned once their
	expiration has passed, so the record stays small over time. On its first
	call an in-memory process returns everything currently active; subsequent
	calls return only alerts that appeared since the previous call.
	"""
	global _BROADCAST_IDS
	alerts = get_alerts(latitude, longitude)
	now = datetime.now(timezone.utc)
	# Drop any whose stored expiration is now in the past.
	_BROADCAST_IDS = {
		alert_id: expires for alert_id, expires in _BROADCAST_IDS.items()
		if expires >= now
	}
	new = []
	for alert in alerts:
		if alert["id"] in _BROADCAST_IDS:
			continue
		new.append(alert)
		_BROADCAST_IDS[alert["id"]] = alert["expiration"]
	return new
