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

# Glyphs available in the Wadamesh OS (as of beta 101)
WADAMESH_GLPYHS = [
	0x1F1F1,  # 🇱
	0x1F308,  # 🌈
	0x1F30A,  # 🌊
	0x1F310,  # 🌐
	0x1F319,  # 🌙
	0x1F31F,  # 🌟
	0x1F320,  # 🌠
	0x1F331,  # 🌱
	0x1F333,  # 🌳
	0x1F334,  # 🌴
	0x1F337,  # 🌷
	0x1F338,  # 🌸
	0x1F339,  # 🌹
	0x1F33A,  # 🌺
	0x1F33F,  # 🌿
	0x1F340,  # 🍀
	0x1F341,  # 🍁
	0x1F342,  # 🍂
	0x1F355,  # 🍕
	0x1F37A,  # 🍺
	0x1F381,  # 🎁
	0x1F382,  # 🎂
	0x1F388,  # 🎈
	0x1F389,  # 🎉
	0x1F38A,  # 🎊
	0x1F3AF,  # 🎯
	0x1F3F3,  # 🏳
	0x1F414,  # 🐔
	0x1F417,  # 🐗
	0x1F426,  # 🐦
	0x1F427,  # 🐧
	0x1F428,  # 🐨
	0x1F42F,  # 🐯
	0x1F430,  # 🐰
	0x1F431,  # 🐱
	0x1F434,  # 🐴
	0x1F435,  # 🐵
	0x1F436,  # 🐶
	0x1F437,  # 🐷
	0x1F438,  # 🐸
	0x1F439,  # 🐹
	0x1F43A,  # 🐺
	0x1F446,  # 👆
	0x1F447,  # 👇
	0x1F448,  # 👈
	0x1F449,  # 👉
	0x1F44A,  # 👊
	0x1F44F,  # 👏
	0x1F450,  # 👐
	0x1F451,  # 👑
	0x1F47F,  # 👿
	0x1F480,  # 💀
	0x1F490,  # 💐
	0x1F493,  # 💓
	0x1F494,  # 💔
	0x1F495,  # 💕
	0x1F496,  # 💖
	0x1F497,  # 💗
	0x1F498,  # 💘
	0x1F499,  # 💙
	0x1F49A,  # 💚
	0x1F49F,  # 💟
	0x1F4A1,  # 💡
	0x1F4A2,  # 💢
	0x1F4A3,  # 💣
	0x1F4A4,  # 💤
	0x1F4A5,  # 💥
	0x1F4A6,  # 💦
	0x1F4A7,  # 💧
	0x1F4A8,  # 💨
	0x1F4A9,  # 💩
	0x1F4AA,  # 💪
	0x1F4AF,  # 💯
	0x1F4F1,  # 📱
	0x1F4F7,  # 📷
	0x1F511,  # 🔑
	0x1F512,  # 🔒
	0x1F513,  # 🔓
	0x1F514,  # 🔔
	0x1F515,  # 🔕
	0x1F517,  # 🔗
	0x1F519,  # 🔙
	0x1F51A,  # 🔚
	0x1F525,  # 🔥
	0x1F534,  # 🔴
	0x1F535,  # 🔵
	0x1F590,  # 🖐
	0x1F595,  # 🖕
	0x1F596,  # 🖖
	0x1F5A4,  # 🖤
	0x1F5FF,  # 🗿
	0x1F600,  # 😀
	0x1F601,  # 😁
	0x1F602,  # 😂
	0x1F603,  # 😃
	0x1F604,  # 😄
	0x1F605,  # 😅
	0x1F606,  # 😆
	0x1F607,  # 😇
	0x1F608,  # 😈
	0x1F609,  # 😉
	0x1F60A,  # 😊
	0x1F60F,  # 😏
	0x1F610,  # 😐
	0x1F611,  # 😑
	0x1F612,  # 😒
	0x1F613,  # 😓
	0x1F614,  # 😔
	0x1F615,  # 😕
	0x1F616,  # 😖
	0x1F617,  # 😗
	0x1F618,  # 😘
	0x1F619,  # 😙
	0x1F61A,  # 😚
	0x1F61F,  # 😟
	0x1F620,  # 😠
	0x1F621,  # 😡
	0x1F622,  # 😢
	0x1F623,  # 😣
	0x1F624,  # 😤
	0x1F625,  # 😥
	0x1F626,  # 😦
	0x1F627,  # 😧
	0x1F628,  # 😨
	0x1F629,  # 😩
	0x1F62A,  # 😪
	0x1F62F,  # 😯
	0x1F630,  # 😰
	0x1F631,  # 😱
	0x1F632,  # 😲
	0x1F633,  # 😳
	0x1F634,  # 😴
	0x1F635,  # 😵
	0x1F636,  # 😶
	0x1F637,  # 😷
	0x1F641,  # 🙁
	0x1F642,  # 🙂
	0x1F643,  # 🙃
	0x1F644,  # 🙄
	0x1F648,  # 🙈
	0x1F649,  # 🙉
	0x1F64A,  # 🙊
	0x1F64F,  # 🙏
	0x1F680,  # 🚀
	0x1F697,  # 🚗
	0x1F698,  # 🚘
	0x1F6A8,  # 🚨
	0x1F910,  # 🤐
	0x1F911,  # 🤑
	0x1F912,  # 🤒
	0x1F913,  # 🤓
	0x1F914,  # 🤔
	0x1F915,  # 🤕
	0x1F916,  # 🤖
	0x1F917,  # 🤗
	0x1F918,  # 🤘
	0x1F919,  # 🤙
	0x1F91A,  # 🤚
	0x1F91F,  # 🤟
	0x1F920,  # 🤠
	0x1F921,  # 🤡
	0x1F922,  # 🤢
	0x1F923,  # 🤣
	0x1F924,  # 🤤
	0x1F925,  # 🤥
	0x1F927,  # 🤧
	0x1F928,  # 🤨
	0x1F929,  # 🤩
	0x1F92A,  # 🤪
	0x1F92F,  # 🤯
	0x1F932,  # 🤲
	0x1F970,  # 🥰
	0x1F971,  # 🥱
	0x1F973,  # 🥳
	0x1F974,  # 🥴
	0x1F975,  # 🥵
	0x1F976,  # 🥶
	0x1F97A,  # 🥺
	0x1F981,  # 🦁
	0x1F984,  # 🦄
	0x1F985,  # 🦅
	0x1F986,  # 🦆
	0x1F989,  # 🦉
	0x231A,  # ⌚
	0x2600,  # ☀
	0x2601,  # ☁
	0x2614,  # ☔
	0x2615,  # ☕
	0x26A0,  # ⚠
	0x26A1,  # ⚡
	0x2705,  # ✅
	0x270A,  # ✊
	0x2714,  # ✔
	0x2716,  # ✖
	0x2728,  # ✨
	0x2744,  # ❄
	0x2753,  # ❓
	0x2754,  # ❔
	0x2755,  # ❕
	0x2757,  # ❗
	0x2763,  # ❣
	0x2764,  # ❤
	0x2795,  # ➕
	0x2796,  # ➖
	0x2797,  # ➗
]


# Every standard icon name the glyph sets must cover.
_STANDARD_NAMES = {
	'sun', 'moon', 'sun_clouds', 'cloud',
	'rain', 'drizzle', 'thunderstorm', 'snow', 'fog',
	'freezing',
	'cyclone', 'flood', 'heat', 'wind', 'dust', 'mask',
	'fire', 'avalanche', 'surf', 'ship', 'info', 'warning',
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
	The compatible set must only use glyphs from well-supported ranges:
	plain ASCII, the U+2600-U+27BF basic-symbols block (safest on mesh
	devices), the U+1F300-U+1F3FF range (used for the moon glyph), and the
	U+FE0F variation selector (appended to the moon emoji).
	"""
	for name, glyph in WEATHER_ICONS_COMPATIBLE.items():
		for ch in glyph:
			cp = ord(ch)
			wadamesh_ok = cp in WADAMESH_GLPYHS
			assert wadamesh_ok, f"Wadamesh does not have glpyh {hex(cp)} for icon {repr(name)} ({ch})"


def test_modern_set_still_uses_colour_emoji():
	"""
The modern set must retain colour emoji (U+1F000+) so nothing is lost on
clients that support it.
	"""
	codepoints = {ord(ch) for glyph in WEATHER_ICONS_MODERN.values() for ch in glyph}
	assert any(0x1F000 <= cp <= 0x1F9FF for cp in codepoints)


def test_get_icon_unknown_name_returns_empty(mocker):
	mocker.patch.object(icon_map.config.general, 'icon_style', 'modern')
	assert get_icon('bogus') == ''


def test_get_weather_icon_unknown_code_returns_empty(mocker):
	mocker.patch.object(icon_map.config.general, 'icon_style', 'modern')
	assert get_weather_icon('zzzz') == ''
	assert get_weather_icon('') == ''
