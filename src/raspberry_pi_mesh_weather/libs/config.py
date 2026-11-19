import yaml
from pathlib import Path
from dataclasses import dataclass


@dataclass
class DisplayConfig:
	enabled: bool = False
	type: str | None = None
	interface: str = 'spi'
	device: int | None = None
	port: int | None = None
	dc_gpio: int | None = None
	reset_gpio: int | None = None
	baud_rate: int | None = None
	reset_delay: bool = True
	rotate: int | None = None
	width: int | None = None
	height: int | None = None


@dataclass
class RadioConfig:
	type: str = 'meshcore'
	interface: str = 'serial'
	port: str = '/dev/ttyUSB0'
	baud_rate: int = 115200
	# Public-key prefix used by the CLI radio (`radio.type: "cli"`) as the
	# sender for un-targeted direct messages.  When left empty, the CLI radio
	# falls back to the first entry of `auth_radios` so authorized commands
	# work by default.
	target: str = ''


@dataclass
class AiConfig:
	"""
	Configuration handler for AI options

	"""
	# Optional in-process command resolver: a small sentence-transformer model
	# classifies unrecognized direct messages into a known command.  Exact
	# command/alias matches are always tried first and win; the model is only
	# consulted when those fail, and it can only pick from the existing command
	# catalog, with replies still produced by the normal commands.  Disabled
	# by default.
	#
	# Anchors are the command functions' docstrings (one phrasing per line);
	# their embeddings are generated once at daemon startup.

	enabled: bool = False
	"""
	Set to True to enable this service; setting to False (default) will prevent any natural language support
	"""

	# Hugging Face model ID (auto-downloaded on first load, or cached if already
	# present) or an absolute path to a local directory containing the model
	# files (for offline Pis).
	model_path: str = 'sentence-transformers/all-MiniLM-L6-v2'
	# Minimum cosine similarity between a message embedding and a command's
	# anchors for it to be considered a match (0.0-1.0; higher is stricter).
	threshold: float = 0.55
	device: str = 'cpu'
	"""
	 device (str, optional): Device (like "cuda", "cpu", "mps", "npu") that should be used for computation.
	"""


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
	region: str | None = None


@dataclass
class WeatherConfig:
	openweather_api_key: str = ''


@dataclass
class GeneralConfig:
	# Icon style used for forecast messages:
	#   'modern'     - colour emoji (best on modern clients)
	#   'compatible' - U+2600-U+27BF block glyphs (safest on mesh devices)
	icon_style: str = 'compatible'
	# Name/organisation operating this service, shown by the 'about' command.
	operated_by: str = ''


@dataclass
class HomeAssistantConfig:
	url: str | None = None
	token: str | None = None
	icons: dict[str, str] | None = None


@dataclass
class MqttConfig:
	host: str = ''
	port: int | None = None
	usage: str | None = None
	topic: str | None = None  # = 'meshcore/{IATA}/{PUBLIC_KEY}/packets'
	username: str | None = None
	password: str | None = None
	websocket: bool = False
	tls: bool = False
	verify_tls: bool = True
	token: bool = False
	token_audience: str | None = None
	token_timeout: int | None = None
	client_prefix: str = 'v1'


@dataclass
class Config:
	display: DisplayConfig
	radio: RadioConfig
	sensors: list[SensorConfig]
	location: LocationConfig
	ai: AiConfig
	weather: WeatherConfig
	general: GeneralConfig
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
		if 'sensors' in raw_data and isinstance(raw_data['sensors'], list):
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
			ai=AiConfig(**raw_data.get('ai', {})),
			weather=WeatherConfig(**raw_data['weather']),
			general=GeneralConfig(**raw_data.get('general', {})),
			home_assistant=HomeAssistantConfig(**raw_data['home_assistant']),
			auth_radios=raw_data['auth_radios'],
			mqtt=mqtts,
		)


# Singleton instance for easy importing
# This ensures the file is only read once per process
config = Config.load(Path(__file__).parent.parent.parent.parent / 'config.yaml')