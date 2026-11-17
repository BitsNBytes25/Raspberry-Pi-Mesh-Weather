"""
Tests for the NWS active-alert client: tracked-value filtering, event-to-icon
resolution through the centralised icon map, dict-shaped get_alerts() return,
and the in-memory, expiration-pruned get_new_alerts() dedup.
"""
import json
from datetime import datetime, timedelta, timezone

import pytest
import requests
from pathlib import Path

from raspberry_pi_mesh_weather.libs import icon_map, weather_alerts
from raspberry_pi_mesh_weather.libs.icon_map import get_icon
from raspberry_pi_mesh_weather.libs.weather_alerts import (
	get_alerts,
	get_new_alerts,
	parse_alert_icon,
)


_FIXTURE_DIR = Path(__file__).parent / '..' / '..' / 'fixtures' / 'api_weather_gov'


@pytest.fixture(autouse=True)
def reset_broadcast_state():
	"""
	Broadcast ids live in module memory; start and end each test clean so the
	dedup state of one test never leaks into the next.
	"""
	weather_alerts._BROADCAST_IDS.clear()
	yield
	weather_alerts._BROADCAST_IDS.clear()


def _load(name):
	# Load a static api.weather.gov response fixture.
	fixture_file = _FIXTURE_DIR / name
	with open(fixture_file, 'r') as f:
		return json.load(f)


def _patch_response(mocker, payload, status_code=200):
	"""
	Return a mock of requests.get that answers with a Response for `payload`.
	"""
	response = requests.Response()
	response.status_code = status_code
	response.json = lambda: payload
	return mocker.patch.object(weather_alerts.requests, 'get', return_value=response)


@pytest.mark.parametrize(
	('event_name', 'icon_name'),
	[
		('Ashfall Warning', 'warning'),
		('Avalanche Warning', 'avalanche'),
		('Blizzard Warning', 'snow'),
		('Blowing Dust Warning', 'dust'),
		('Civil Danger Warning', 'warning'),
		('Civil Emergency Message', 'warning'),
		('Coastal Flood Warning', 'flood'),
		('Dust Storm Warning', 'dust'),
		('Earthquake Warning', 'warning'),
		('Evacuation Immediate', 'warning'),
		('Extreme Heat Warning', 'heat'),
		('Extreme Cold Warning', 'freezing'),
		('Extreme Fire Danger', 'fire'),
		('Extreme Wind Warning', 'wind'),
		('Fire Warning', 'fire'),
		('Flash Flood Warning', 'flood'),
		('Flood Warning', 'flood'),
		('Hazardous Materials Warning', 'warning'),
		('Hazardous Seas Warning', 'ship'),
		('Heavy Freezing Spray Warning', 'freezing'),
		('High Surf Warning', 'surf'),
		('High Wind Warning', 'wind'),
		('Hurricane Force Wind Warning', 'cyclone'),
		('Hurricane Warning', 'cyclone'),
		('Ice Storm Warning', 'snow'),
		('Lake Effect Snow Warning', 'snow'),
		('Lakeshore Flood Warning', 'flood'),
		('Law Enforcement Warning', 'warning'),
		('Local Area Emergency', 'warning'),
		('Nuclear Power Plant Warning', 'warning'),
		('Radiological Hazard Warning', 'warning'),
		('Red Flag Warning', 'fire'),
		('Severe Thunderstorm Warning', 'thunderstorm'),
		('Shelter In Place Warning', 'warning'),
		('Snow Squall Warning', 'snow'),
		('Special Marine Warning', 'ship'),
		('Storm Surge Warning', 'flood'),
		('Storm Warning', 'warning'),
		('Tornado Warning', 'cyclone'),
		('Tropical Storm Warning', 'cyclone'),
		('Tsunami Warning', 'flood'),
		('Typhoon Warning', 'cyclone'),
		('Winter Storm Warning', 'snow'),
	],
)
def test_parse_alert_icon_modern(event_name, icon_name, mocker):
	"""
	Exact match per tracked event resolves to the expected standard glyph via
	get_icon(); the modern set gives one distinct glyph per name.
	"""
	mocker.patch.object(icon_map.config.general, 'icon_style', 'modern')
	assert parse_alert_icon(event_name) == get_icon(icon_name)


def test_parse_alert_icon_unknown(mocker):
	mocker.patch.object(icon_map.config.general, 'icon_style', 'modern')
	assert parse_alert_icon('Some Totally Untracked Event') == get_icon('warning')
	assert parse_alert_icon('') == get_icon('warning')


@pytest.mark.parametrize(
	('fixture_name', 'icon_name'),
	[
		('severe_flood_warning.json', 'flood'),
		('severe_tornado_warning.json', 'cyclone'),
		('severe_thunderstorm_warning.json', 'thunderstorm'),
	],
)
def test_get_alerts_tracked_fixture(mocker, fixture_name, icon_name):
	"""
	A tracked alert (event + severity + urgency + certainty all in the tracked
	sets) comes back as a {icon, title, id, expiration} record.
	"""
	payload = _load(fixture_name)
	_patch_response(mocker, payload)
	alerts = get_alerts(33.47, -87.44)

	props = payload['features'][0]['properties']
	assert alerts == [
		{
			'icon': get_icon(icon_name),
			'title': props['headline'],
			'id': props['id'],
			'expiration': datetime.fromisoformat(props['expires']),
		}
	]


@pytest.mark.parametrize(
	'fixture_name',
	[
		'minor_small_craft_advisory.json',  # Small Craft Advisory - not tracked
		'severe_freeze_warning.json',       # Freeze Warning - not tracked
		'minor_frost_advisory.json',        # Frost Advisory / Minor - not tracked
		'moderate_fog.json',                # Dense Fog Advisory / Moderate - not tracked
		'special_weather_statement.json',   # Special Weather Statement - not tracked
		'severe_flood_watch.json',          # Flood Watch - not tracked
	],
)
def test_get_alerts_untracked_fixture(mocker, fixture_name):
	"""
	Events (or severity/urgency/certainty) outside the tracked sets are
	ignored: nothing is returned for them.
	"""
	payload = _load(fixture_name)
	_patch_response(mocker, payload)
	assert get_alerts(33.47, -87.44) == []


def test_get_alerts_empty_features(mocker):
	_patch_response(mocker, {'features': []})
	assert get_alerts(33.47, -87.44) == []


def test_get_alerts_bad_response(mocker):
	_patch_response(mocker, {}, status_code=401)
	assert get_alerts(33.47, -87.44) == []


def test_get_alerts_network_failure(mocker):
	mocker.patch.object(
		weather_alerts.requests,
		'get',
		side_effect=requests.exceptions.ConnectionError('no connectivity')
	)
	assert get_alerts(33.47, -87.44) == []


def test_get_new_alerts_first_call_all_then_none(mocker):
	"""
	First call broadcasts everything currently active and remembers it; the
	next call returns nothing.
	"""
	payload = _load('severe_flood_warning.json')
	# Update the payload to have an expiration in the future
	payload['features'][0]['properties']['expires'] = (datetime.now().astimezone() + timedelta(minutes=10)).isoformat()
	props = payload['features'][0]['properties']
	_patch_response(mocker, payload)

	first = get_new_alerts(33.47, -87.44)
	assert len(first) == 1
	assert first[0]['id'] == props['id']
	assert props['id'] in weather_alerts._BROADCAST_IDS

	second = get_new_alerts(33.47, -87.44)
	assert second == []


def test_get_new_alerts_mixed_returns_only_new(mocker):
	"""
	Already-broadcast alerts are skipped; only newly-appeared alerts are
	returned (and remembered).
	"""
	weather_alerts._BROADCAST_IDS = {
		'urn:already-broadcast.001': datetime.now(timezone.utc) + timedelta(days=30),
	}
	payload = {
		'features': [
			{
				'type': 'Feature',
				'properties': {
					'id': 'urn:already-broadcast.001',
					'expires': '2026-12-31T18:00:00-06:00',
					'severity': 'Severe',
					'urgency': 'Immediate',
					'certainty': 'Observed',
					'event': 'Flood Warning',
					'headline': 'Already Broadcast Flood Warning',
				},
			},
			{
				'type': 'Feature',
				'properties': {
					'id': 'urn:new-alert.001',
					'expires': '2026-12-31T18:00:00-06:00',
					'severity': 'Severe',
					'urgency': 'Immediate',
					'certainty': 'Observed',
					'event': 'Tornado Warning',
					'headline': 'Brand New Tornado Warning',
				},
			},
		]
	}
	_patch_response(mocker, payload)

	new = get_new_alerts(33.47, -87.44)
	assert len(new) == 1
	assert new[0]['id'] == 'urn:new-alert.001'
	assert 'urn:already-broadcast.001' in weather_alerts._BROADCAST_IDS
	assert 'urn:new-alert.001' in weather_alerts._BROADCAST_IDS


def test_get_new_alerts_prunes_expired(mocker):
	"""
	Ids whose stored expiration is in the past are dropped from memory, so the
	record stays bounded; unexpired ids are retained.
	"""
	weather_alerts._BROADCAST_IDS = {
		'urn:expired.001': datetime(2020, 1, 1, tzinfo=timezone.utc),
		'urn:current.001': datetime(2030, 1, 1, tzinfo=timezone.utc),
	}
	_patch_response(mocker, {'features': []})

	get_new_alerts(33.47, -87.44)

	assert 'urn:expired.001' not in weather_alerts._BROADCAST_IDS
	assert 'urn:current.001' in weather_alerts._BROADCAST_IDS
