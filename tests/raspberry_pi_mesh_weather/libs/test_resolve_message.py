"""
Tests for `resolve_message` — direct-message text resolution: exact name/
alias match first, AI fallback only when exact resolution fails.
"""

from unittest.mock import Mock

import raspberry_pi_mesh_weather.libs.commands.handler as handler_module
from raspberry_pi_mesh_weather.libs.commands import get_command, resolve_message


def test_resolve_message_exact_match_short_circuits_ai(mocker):
	spy = Mock()
	mocker.patch.object(handler_module, '_ai_resolve', spy)
	result = resolve_message('temp')
	assert result is get_command('temp')
	spy.assert_not_called()


def test_resolve_message_exact_alias_short_circuits_ai(mocker):
	spy = Mock()
	mocker.patch.object(handler_module, '_ai_resolve', spy)
	result = resolve_message('pres')
	assert result is get_command('pres')
	spy.assert_not_called()


def test_resolve_message_exact_group_command(mocker):
	spy = Mock()
	mocker.patch.object(handler_module, '_ai_resolve', spy)
	result = resolve_message('!temp')
	assert result is get_command('!temp')
	spy.assert_not_called()


def test_resolve_message_falls_back_to_ai_on_unknown_text(mocker):
	mocker.patch.object(handler_module, '_ai_resolve', return_value='temp')
	result = resolve_message('what is the temperature?')
	assert result is get_command('temp')


def test_resolve_message_falls_back_to_ai_alias(mocker):
	mocker.patch.object(handler_module, '_ai_resolve', return_value='pres')
	result = resolve_message('give me the pressure')
	assert result is get_command('pres')


def test_resolve_message_ai_unknown_returns_none(mocker):
	mocker.patch.object(handler_module, '_ai_resolve', return_value=None)
	assert resolve_message('what is the temperature?') is None


def test_resolve_message_ai_garbage_returns_none(mocker):
	mocker.patch.object(handler_module, '_ai_resolve', return_value='not-a-command')
	assert resolve_message('what is the temperature?') is None


def test_resolve_message_without_ai_returns_none_on_unknown(mocker):
	# AI unavailable (no service registered) is treated as "no match";
	# exact commands still work without it.
	mocker.patch.object(handler_module, '_ai_resolve', return_value=None)
	assert resolve_message('hello') is None
	result = resolve_message('temp')
	assert result is get_command('temp')
