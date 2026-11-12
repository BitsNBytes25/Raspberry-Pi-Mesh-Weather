from raspberry_pi_mesh_weather.libs import commands


def _patch_readings(mocker, temp, humidity, pressure, change, label):
	mocker.patch.object(commands, 'get_temperature', return_value=temp)
	mocker.patch.object(commands, 'get_humidity', return_value=humidity)
	mocker.patch.object(commands, 'get_pressure', return_value=pressure)
	mocker.patch.object(commands, 'get_pressure_change', return_value=change)
	location = mocker.patch.object(commands, 'config')
	location.location.label = label
	return commands.cmd_all_sensors(None)


def test_all_sensors_all_readings_stable(mocker):
	result = _patch_readings(mocker, 22.1, 45.3, 1012.3, 0, 'cbus')

	assert result.success is True
	assert result.has_data is True
	assert result.message == (
		'☀️ Weather in cbus:\n'
		'22.1°C (72°F) | 45.3% humidity | 1012.3 hPa (stable)'
	)


def test_all_sensors_pressure_rising(mocker):
	result = _patch_readings(mocker, 23.5, 40.0, 1012.7, 1, 'cbus')

	assert result.success is True
	assert result.message == (
		'☀️ Weather in cbus:\n'
		'23.5°C (74°F) | 40.0% humidity | 1012.7 hPa (rising)'
	)


def test_all_sensors_pressure_falling(mocker):
	result = _patch_readings(mocker, 21.0, 55.0, 1009.8, -1, 'cbus')

	assert result.success is True
	assert result.message == (
		'🌧️ Weather in cbus:\n'
		'21.0°C (70°F) | 55.0% humidity | 1009.8 hPa (falling)'
	)


def test_all_sensors_high_humidity_cloudy(mocker):
	result = _patch_readings(mocker, 29.5, 75.0, 1011.0, 0, 'cbus')

	assert result.success is True
	assert result.message == (
		'⛅ Weather in cbus:\n'
		'29.5°C (85°F) | 75.0% humidity | 1011.0 hPa (stable)'
	)


def test_all_sensors_freezing_takes_precedence(mocker):
	result = _patch_readings(mocker, -2.5, 30.0, 1012.0, 1, 'cbus')

	assert result.success is True
	assert result.message == (
		'🥶 Weather in cbus:\n'
		'-2.5°C (28°F) | 30.0% humidity | 1012.0 hPa (rising)'
	)


def test_all_sensors_missing_humidity(mocker):
	result = _patch_readings(mocker, 21.0, None, 1012.3, 0, 'cbus')

	assert result.success is True
	assert result.message == (
		'☀️ Weather in cbus:\n'
		'21.0°C (70°F) | 1012.3 hPa (stable)'
	)


def test_all_sensors_missing_location_label(mocker):
	result = _patch_readings(mocker, 20.0, 50.0, 1013.0, 0, '')

	assert result.success is True
	assert result.message == (
		'☀️ Current weather here:\n'
		'20.0°C (68°F) | 50.0% humidity | 1013.0 hPa (stable)'
	)


def test_all_sensors_missing_temperature(mocker):
	result = _patch_readings(mocker, None, 78.0, 1010.5, -1, 'cbus')

	assert result.success is True
	assert result.message == (
		'🌧️ Weather in cbus:\n'
		'78.0% humidity | 1010.5 hPa (falling)'
	)


def test_all_sensors_no_readings(mocker):
	result = _patch_readings(mocker, None, None, None, 0, 'cbus')

	assert result.success is True
	assert result.has_data is False
	assert result.message == 'Sorry, but no sensor data is available'
