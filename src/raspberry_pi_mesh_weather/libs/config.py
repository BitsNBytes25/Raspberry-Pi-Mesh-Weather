import yaml
from pathlib import Path
from dataclasses import dataclass


@dataclass
class DisplayConfig:
	enabled: bool = False
	type: str = 'spi'
	device: int = 0
	port: int = 0
	dc_gpio: int = 25
	reset_gpio: int = 24
	baud_rate: int = 8000000
	reset_delay: bool = True


@dataclass
class RadioConfig:
	type: str = 'meshcore'
	conn: str = 'serial'
	port: str = '/dev/ttyUSB0'
	baud_rate: int = 115200


@dataclass
class SensorConfig:
	type: str
	port: int | None = None
	address: int | None = None
	baud_rate: int | None = None

@dataclass
class LocationConfig:
	altitude: int | None = None
	label: str = ''
	lat: float | None = None
	lon: float | None = None
	iata: str = 'XYZ'


@dataclass
class WeatherConfig:
	openweather_api_key: str = ''


@dataclass
class HomeAssistantConfig:
	url: str = ''
	token: str = ''


@dataclass
class MqttConfig:
	host: str = ''
	port: int | None = None
	topic: str = 'meshcore/{IATA}/{PUBLIC_KEY}/packets'
	username: str | None = None
	password: str | None = None
	websocket: bool = False
	tls: bool = False
	verify_tls: bool = True
	token: bool = False
	token_audience: str | None = None
	client_prefix: str = 'v1'


@dataclass
class Config:
	display: DisplayConfig
	radio: RadioConfig
	sensors: list[SensorConfig]
	location: LocationConfig
	weather: WeatherConfig
	home_assistant: HomeAssistantConfig
	auth_radios: list[str]
	mqtt: list[MqttConfig]

	@classmethod
	def load(cls, config_path: Path):
		if not config_path.exists():
			raise FileNotFoundError(f"Configuration file not found at {config_path}")

		with open(config_path, 'r') as f:
			raw_data = yaml.safe_load(f)

		sensors = []
		for sensor in raw_data['sensors']:
			sensors.append(SensorConfig(**sensor))

		mqtts = []
		for mqtt in raw_data['mqtt']:
			mqtts.append(MqttConfig(**mqtt))

		return cls(
			display=DisplayConfig(**raw_data['display']),
			radio=RadioConfig(**raw_data['radio']),
			sensors=sensors,
			location=LocationConfig(**raw_data['location']),
			weather=WeatherConfig(**raw_data['weather']),
			home_assistant=HomeAssistantConfig(**raw_data['home_assistant']),
			auth_radios=raw_data['auth_radios'],
			mqtt=mqtts,
		)


# Singleton instance for easy importing
# This ensures the file is only read once per process
config = Config.load(Path(__file__).parent.parent.parent.parent / 'config.yaml')