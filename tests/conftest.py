import pytest
import json
from pathlib import Path


@pytest.fixture
def mock_payload_flood_advert():
	# Load the payload for a flood advert
	fixture = Path(__file__).parent / 'fixtures' / 'meshcore' / 'payload_flood_advert.json'
	with open(fixture, 'r') as f:
		return json.load(f)


@pytest.fixture
def mock_payload_direct_message():
	# Load the payload for a direct message
	fixture = Path(__file__).parent / 'fixtures' / 'meshcore' / 'payload_direct_message.json'
	with open(fixture, 'r') as f:
		return json.load(f)


@pytest.fixture
def columbus_afternoon():
	# Load a good OpenWeatherMap forecast response for Columbus, OH
	fixture = Path(__file__).parent / 'fixtures' / 'api_openweathermap_org' / 'columbus_afternoon.json'
	with open(fixture, 'r') as f:
		return json.load(f)


@pytest.fixture
def columbus_morning():
	# Load a good OpenWeatherMap forecast response for Columbus, OH (morning window)
	fixture = Path(__file__).parent / 'fixtures' / 'api_openweathermap_org' / 'columbus_morning.json'
	with open(fixture, 'r') as f:
		return json.load(f)
