"""
Tests for `resolve_message` — direct-message text resolution: exact name/
alias match first, then the registered message handlers (the AI command
resolver registers itself as one).
"""

from unittest.mock import Mock

import raspberry_pi_mesh_weather.libs.commands.handler as handler_module
from raspberry_pi_mesh_weather.libs.commands import get_command, resolve_message


def test_resolve_message_exact_match_short_circuits_handlers(mocker):
	spy = Mock()
	mocker.patch.object(handler_module, '_message_handlers', [spy])
	result = resolve_message('temp')
	assert result is get_command('temp')
	spy.assert_not_called()


def test_resolve_message_exact_alias_short_circuits_handlers(mocker):
	spy = Mock()
	mocker.patch.object(handler_module, '_message_handlers', [spy])
	result = resolve_message('pres')
	assert result is get_command('pres')
	spy.assert_not_called()


def test_resolve_message_exact_group_command(mocker):
	spy = Mock()
	mocker.patch.object(handler_module, '_message_handlers', [spy])
	result = resolve_message('!temp')
	assert result is get_command('!temp')
	spy.assert_not_called()


def test_resolve_message_falls_back_to_handler(mocker):
	mocker.patch.object(handler_module, '_message_handlers', [lambda text: get_command('temp')])
	result = resolve_message('what is the temperature?')
	assert result is get_command('temp')


def test_resolve_message_falls_back_to_handler_alias(mocker):
	mocker.patch.object(handler_module, '_message_handlers', [lambda text: get_command('pres')])
	result = resolve_message('give me the pressure')
	assert result is get_command('pres')


def test_resolve_message_handler_unknown_returns_none(mocker):
	mocker.patch.object(handler_module, '_message_handlers', [lambda text: None])
	assert resolve_message('what is the temperature?') is None


def test_resolve_message_handler_garbage_returns_none(mocker):
	mocker.patch.object(handler_module, '_message_handlers', [lambda text: 'not-a-command'])
	assert resolve_message('what is the temperature?') is None


def test_resolve_message_no_handler_returns_none_on_unknown(mocker):
	mocker.patch.object(handler_module, '_message_handlers', [])
	assert resolve_message('hello') is None
	result = resolve_message('temp')
	assert result is get_command('temp')


def test_resolve_message_first_handler_none_second_wins(mocker):
	mocker.patch.object(
		handler_module,
		'_message_handlers',
		[lambda text: None, lambda text: get_command('uptime')],
	)
	result = resolve_message('how long has the device been up')
	assert result is get_command('uptime')
