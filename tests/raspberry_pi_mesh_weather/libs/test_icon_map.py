"""
Tests for the WMO icon library: standard-name glyph sets and the
OpenWeatherMap code -> standard-name -> glyph translation.
"""

import pytest
VS = chr(0xFE0F)

from raspberry_pi_mesh_weather.libs import icon_map
from raspberry_pi_mesh_weather.libs.icon_map import (
	OWM_ICON_NAMES,
	STANDARD_ICON_NAMES,
	WEATHER_ICONS_COMPATIBLE,
	WEATHER_ICONS_MODERN,
	get_icon,
	get_weather_icon,
)


# Every standard icon name the glyph sets must cover.
_STANDARD_NAMES = {
	'sun', 'moon', 'sun_clouds', 'cloud',
	'rain', 'drizzle', 'thunderstorm', 'snow', 'fog',
}

# Every OpenWeatherMap icon code this project is expected to render.
_OWM_CODES = {
	'01d', '01n', '02d', '02n', '03d', '03n', '04d', '04n',
	'09d', '09n', '10d', '10n', '11d', '11n', '13d', '13n',
	'45d', '45n', '48d', '48n', '50d', '50n',
	'80d', '80n', '81d', '81n',
	'95d', '95n', '96d', '96n', '99d', '99n',
}


def test_standard_names_match_expected():
	"""
The module's public standard-name list must match the expected names, so a
future change to either side is caught here rather than silently.
	"""
	assert set(STANDARD_ICON_NAMES) == _STANDARD_NAMES


def test_both_maps_are_keyed_by_standard_names():
	"""
Both glyph sets must be keyed exactly by the standard names, so the
library is decoupled from any one feed codes.
	"""
	assert set(WEATHER_ICONS_MODERN) == set(STANDARD_ICON_NAMES)
	assert set(WEATHER_ICONS_COMPATIBLE) == set(STANDARD_ICON_NAMES)
	for name in STANDARD_ICON_NAMES:
		assert WEATHER_ICONS_MODERN[name], 'empty glyph for ' + repr(name)
		assert WEATHER_ICONS_COMPATIBLE[name], 'empty glyph for ' + repr(name)


def test_owm_codes_cover_expected_set():
	"""
OWM_ICON_NAMES must handle every icon code this project expects and nothing
else, so a feed code is never silently dropped.
	"""
	assert set(OWM_ICON_NAMES) == _OWM_CODES


def test_owm_names_resolve_to_standard_names():
	"""
Every OpenWeatherMap code must map to a valid standard icon name, so the
translation can never leak a feed-specific code into the glyph sets.
	"""
	for code, name in OWM_ICON_NAMES.items():
		assert name in STANDARD_ICON_NAMES, (code, name)


def test_compatible_glyphs_are_widely_supported():
	"""
The compatible set must only use glyphs from the U+2600-U+27BF block (or
plain ASCII), which is the most broadly supported range on mesh devices.
	"""
	for name, glyph in WEATHER_ICONS_COMPATIBLE.items():
		for ch in glyph:
			ok = ord(ch) < 0x80 or (0x2600 <= ord(ch) <= 0x27BF)
			assert ok, 'name ' + repr(name) + ' uses unsupported glyph ' + repr(ch)


def test_modern_set_still_uses_colour_emoji():
	"""
The modern set must retain colour emoji (U+1F000+) so nothing is lost on
clients that support it.
	"""
	codepoints = {ord(ch) for glyph in WEATHER_ICONS_MODERN.values() for ch in glyph}
	assert any(0x1F000 <= cp <= 0x1F9FF for cp in codepoints)


def test_get_icon_modern_glyphs(mocker):
	mocker.patch.object(icon_map.config.general, 'icon_style', 'modern')
	assert get_icon('sun') == chr(0x2600) + VS
	assert get_icon('moon') == chr(0x1F319) + VS
	assert get_icon('rain') == chr(0x1F327) + VS
	assert get_icon('drizzle') == chr(0x1F326) + VS
	assert get_icon('snow') == chr(0x2744) + VS
	assert get_icon('thunderstorm') == chr(0x26C8) + VS
	assert get_icon('fog') == chr(0x1F32B) + VS


def test_get_icon_compatible_glyphs(mocker):
	mocker.patch.object(icon_map.config.general, 'icon_style', 'compatible')
	assert get_icon('sun') == chr(0x2600)
	assert get_icon('moon') == chr(0x263E)
	assert get_icon('sun_clouds') == chr(0x26C5)
	assert get_icon('cloud') == chr(0x2601)
	assert get_icon('rain') == chr(0x2614)
	assert get_icon('drizzle') == chr(0x2602)
	assert get_icon('thunderstorm') == chr(0x26C8)
	assert get_icon('snow') == chr(0x2744)
	assert get_icon('fog') == chr(0x2601)


def test_get_icon_unknown_name_returns_empty(mocker):
	mocker.patch.object(icon_map.config.general, 'icon_style', 'modern')
	assert get_icon('bogus') == ''


def test_get_weather_icon_translates_owm_codes_modern(mocker):
	mocker.patch.object(icon_map.config.general, 'icon_style', 'modern')
	# 09d -> rain; 10d -> drizzle; 50d -> fog; 01d -> sun; 13d -> snow.
	assert get_weather_icon('09d') == chr(0x1F327) + VS
	assert get_weather_icon('10d') == chr(0x1F326) + VS
	assert get_weather_icon('50d') == chr(0x1F32B) + VS
	assert get_weather_icon('01d') == chr(0x2600) + VS
	assert get_weather_icon('13d') == chr(0x2744) + VS


def test_get_weather_icon_translates_owm_codes_compatible(mocker):
	mocker.patch.object(icon_map.config.general, 'icon_style', 'compatible')
	assert get_weather_icon('09d') == chr(0x2614)   # rain -> umbrella w/ drops
	assert get_weather_icon('10d') == chr(0x2602)   # drizzle -> umbrella
	assert get_weather_icon('50d') == chr(0x2601)   # fog -> cloud
	assert get_weather_icon('01d') == chr(0x2600)
	assert get_weather_icon('11d') == chr(0x26C8)
	assert get_weather_icon('80d') == chr(0x2744)   # snow shower -> snowflake


def test_get_weather_icon_unknown_code_returns_empty(mocker):
	mocker.patch.object(icon_map.config.general, 'icon_style', 'modern')
	assert get_weather_icon('zzzz') == ''
	assert get_weather_icon('') == ''


def test_get_weather_icon_honours_shipped_default_style():
	# No patching: exercises the real default ('compatible') from the
	# dataclass / config.yaml.
	assert get_weather_icon('10d') == chr(0x2602)
	assert get_weather_icon('09d') == chr(0x2614)
