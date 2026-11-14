"""WMO weather icon library.

The glyph sets are keyed by standard, source-independent icon names.  This
keeps the icon library decoupled from any one weather feed: a feed-specific
code is translated to a standard name via the internal OWM_ICON_NAMES map,
and the glyph sets never know about it.

Two glyph sets are available, selected by the `general.icon_style` config
option:

  * modern     - colour emoji.  Best on modern clients, but some glyphs are
                 absent from limited fonts and render as "*" .
  * compatible - basic symbols from the U+2600-U+27BF Unicode block, the widest
                 range of supported fonts.  Safe on (hopefully) every mesh device.

`get_icon(name)` is the source-agnostic API.  `get_weather_icon()` is the
OpenWeatherMap-specific convenience bridge used by the forecast client."""

from .config import config

# Authoritative, ordered list of standard icon names.  Order is meaningful
# and reused directly by consumers (e.g. the `icons` diagnostic command) so the
# glyph set and its display sequence live in one place.
STANDARD_ICON_NAMES = [
	'cloud',
	'drizzle',
	'fog',
	'freezing',
	'moon',
	'rain',
	'snow',
	'sun',
	'sun_clouds',
	'thunderstorm',
]

OWM_ICON_NAMES = {
	'01d': 'sun',
	'01n': 'moon',
	'02d': 'sun_clouds',
	'02n': 'cloud',
	'03d': 'sun_clouds',
	'03n': 'cloud',
	'04d': 'cloud',
	'04n': 'cloud',
	'09d': 'rain',
	'09n': 'rain',
	'10d': 'drizzle',
	'10n': 'drizzle',
	'11d': 'thunderstorm',
	'11n': 'thunderstorm',
	'13d': 'snow',
	'13n': 'snow',
	'45d': 'fog',
	'45n': 'fog',
	'48d': 'fog',
	'48n': 'fog',
	'50d': 'fog',
	'50n': 'fog',
	'80d': 'snow',
	'80n': 'snow',
	'81d': 'snow',
	'81n': 'snow',
	'95d': 'thunderstorm',
	'95n': 'thunderstorm',
	'96d': 'thunderstorm',
	'96n': 'thunderstorm',
	'99d': 'thunderstorm',
	'99n': 'thunderstorm'
}

WEATHER_ICONS_MODERN = {
	'sun': '☀️',
	'moon': '🌙️',
	'sun_clouds': '⛅️',
	'cloud': '☁️',
	'rain': '🌧️',
	'drizzle': '🌦️',
	'thunderstorm': '⛈️',
	'snow': '❄️',
	'freezing': '🥶️',
	'fog': '🌫️'
}

# These icons are tested working on the T-Deck with Wadamesh
# - https://github.com/ALLFATHER-BV/wadamesh
WEATHER_ICONS_COMPATIBLE = {
	'sun': '☀',          # U+2600 (Black Sun with Rays - worked in your compatible set)
	'moon': '🌙️',          # Simple text character (replaces failing crescent ☾)
	'sun_clouds': '☀',   # Combined text/symbol representation
	'cloud': '☁',         # U+2601 (Cloud - worked)
	'rain': '☔',         # U+2614 (Umbrella with Rain Drops - worked in compatible)
	'drizzle': '☔',       # U+2602 (Umbrella - let's verify or use drop symbol below)
	'thunderstorm': '⚡', # U+26A1 (High-voltage sign / Lightning bolt - usually well supported)
	'snow': '❄',         # U+2744 (Snowflake - worked)
	'freezing': '❄❄',     # U+2744 × 2 (double snowflake for extreme cold)
	'fog': '☁'            # Horizontal lines symbol (often used for fog/mist in terminals)
}

def _icon_maps():
	"""
	Return the glyph set for the currently configured icon style.
	"""

	icon_maps = {
		'modern': WEATHER_ICONS_MODERN,
		'compatible': WEATHER_ICONS_COMPATIBLE,
	}
	return icon_maps.get(config.general.icon_style, WEATHER_ICONS_COMPATIBLE)

def get_icon(name):
	"""
	Resolve a standard icon name to a display glyph in the active style.

	:param name: one of the standard icon names (e.g. "rain").
	:return: the glyph to display, or an empty string if the name is unknown.
	"""

	return _icon_maps().get(name, '')

def get_weather_icon(owm_code):
	"""
	Resolve an OpenWeatherMap icon code to a display glyph.

	Translated through the standard icon names, so the glyph sets never
	need to know about OpenWeatherMap.

	:param owm_code: OpenWeatherMap icon code (e.g. "09d").
	:return: the glyph to display, or an empty string for unknown codes.
	"""

	return get_icon(OWM_ICON_NAMES.get(owm_code, ''))
