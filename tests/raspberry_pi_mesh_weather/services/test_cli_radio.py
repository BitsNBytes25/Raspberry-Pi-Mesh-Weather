"""
Tests for the CLI radio (services/radios/cli_radio.py).

The CLI radio is a hardware-free development "radio": it reads lines from
stdin, treats each one as a *direct message*, resolves it through
``resolve_message`` (exact/alias match, then the opt-in AI resolver), executes
the command with the given target, and prints the reply to the terminal.

These tests cover line-parsing, default-target resolution, reply execution,
broadcast output, the auth-check path, and the interactive ``run()`` loop
(driven by a fake stdin).  AI is disabled in the test config, so
``resolve_message`` falls back to exact/alias dispatch deterministically.
"""

import pytest

from raspberry_pi_mesh_weather.libs.config import config
from raspberry_pi_mesh_weather.libs.commands import CommandResponseNoData
from raspberry_pi_mesh_weather.services.service import ShutdownRequested
import raspberry_pi_mesh_weather.services.radios.cli_radio as cli_radio
from raspberry_pi_mesh_weather.services.radios.cli_radio import CliRadio


# --- _parse ---------------------------------------------------------------


def test_parse_plain_line():
	assert cli_radio.CliRadio._parse('temp') == ('', 'temp')


def test_parse_targeted_line():
	assert cli_radio.CliRadio._parse('@abcd1234 temp') == ('abcd1234', 'temp')


def test_parse_target_with_multiword_message():
	assert cli_radio.CliRadio._parse('@abcd1234 what is the temperature') == (
		'abcd1234',
		'what is the temperature',
	)


def test_parse_target_only_no_message():
	assert cli_radio.CliRadio._parse('@abcd1234') == ('abcd1234', '')


def test_parse_bare_at_symbol():
	assert cli_radio.CliRadio._parse('@') == ('', '')


# --- _default_target ------------------------------------------------------


def test_default_target_prefers_radio_target(monkeypatch):
	monkeypatch.setattr(config.radio, 'target', 'explicit-target')
	# ensure auth_radios would be a fallback but is not used
	assert CliRadio()._default_target() == 'explicit-target'


def test_default_target_falls_back_to_first_auth_radio(monkeypatch):
	# radio.target is '' by default; auth_radios[0] is the fallback
	monkeypatch.setattr(config.radio, 'target', '')
	assert CliRadio()._default_target() == config.auth_radios[0]


def test_default_target_empty_when_no_auth_radios(monkeypatch):
	monkeypatch.setattr(config, 'auth_radios', [])
	monkeypatch.setattr(config.radio, 'target', '')
	assert CliRadio()._default_target() == ''


# --- _reply ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_reply_resolves_and_executes_ping():
	# 'ping' is a direct command returning 'pong' with no side effects.
	reply = await CliRadio()._reply('', 'ping')
	assert reply == 'pong'


@pytest.mark.asyncio
async def test_reply_unresolvable_returns_fallback():
	reply = await CliRadio()._reply('', 'nonsense-command-xyz')
	assert reply == cli_radio.FALLBACK_MESSAGE


@pytest.mark.asyncio
async def test_reply_no_data_returns_empty(monkeypatch):
	def fake_resolve(text):
		def cmd(target):
			return CommandResponseNoData()
		return cmd

	monkeypatch.setattr(cli_radio, 'resolve_message', fake_resolve)
	reply = await CliRadio()._reply('', 'x')
	assert reply == ''


@pytest.mark.asyncio
async def test_reply_enforces_auth_check(monkeypatch):
	# 'reboot' is an auth=True command; it should only succeed for a radio
	# in auth_radios.  The wrapper applies the auth check against the target
	# before running the command body.
	monkeypatch.setattr(config, 'auth_radios', ['4a4fe'])
	authorized = await CliRadio()._reply('4a4fe', 'reboot')
	assert authorized == 'Reboot scheduled'
	unauthorized = await CliRadio()._reply('99999', 'reboot')
	assert 'not authorized' in unauthorized
	assert unauthorized != 'Reboot scheduled'


# --- broadcast / load / stop ----------------------------------------------


@pytest.mark.asyncio
async def test_load_returns_true():
	assert await CliRadio().load() is True


@pytest.mark.asyncio
async def test_stop_sets_running_false():
	radio = CliRadio()
	radio.running = True
	await radio.stop()
	assert radio.running is False


@pytest.mark.asyncio
async def test_broadcast_prints_to_stdout(capsys):
	radio = CliRadio()
	await radio.broadcast('line one\nline two')
	out = capsys.readouterr().out
	assert '[broadcast]' in out
	assert 'line one' in out
	assert 'line two' in out


# --- run() loop -----------------------------------------------------------


def _fake_input(lines):
	"""
	Return a function that yields the given lines (each returned as-is) then
	raises ``EOFError``.  It is installed as ``cli_radio.input`` (a module-level
	shadow of the builtin) so that ``run()`` reads it.
	"""

	it = iter(lines)

	def fake_input(prompt=''):
		try:
			return next(it)
		except StopIteration:
			raise EOFError

	return fake_input


@pytest.mark.asyncio
async def test_run_exits_on_quit(monkeypatch, capsys):
	monkeypatch.setattr(cli_radio, 'input', _fake_input(['quit\n']), raising=False)
	radio = CliRadio()
	radio.running = True
	with pytest.raises(ShutdownRequested):
		await radio.run()
	out = capsys.readouterr().out
	# The banner is printed before the prompt loop.
	assert 'CLI Radio' in out


@pytest.mark.asyncio
async def test_run_processes_messages_then_quit(monkeypatch, capsys):
	monkeypatch.setattr(
		cli_radio, 'input', _fake_input(['ping\n', '?\n', 'quit\n']),
		raising=False,
	)
	radio = CliRadio()
	radio.running = True
	with pytest.raises(ShutdownRequested):
		await radio.run()
	out = capsys.readouterr().out
	# 'ping' reply + banner (printed on start and again on '?').
	assert 'pong' in out
	assert 'CLI Radio' in out


@pytest.mark.asyncio
async def test_run_exits_on_eof(monkeypatch, capsys):
	# One line (ping) then EOF (iterator exhausted) -> ShutdownRequested.
	monkeypatch.setattr(
		cli_radio, 'input', _fake_input(['ping\n']),
		raising=False,
	)
	radio = CliRadio()
	radio.running = True
	with pytest.raises(ShutdownRequested):
		await radio.run()
	out = capsys.readouterr().out
	assert 'pong' in out


@pytest.mark.asyncio
async def test_run_skips_empty_and_unknown_lines_then_quit(monkeypatch):
	monkeypatch.setattr(
		cli_radio, 'input', _fake_input(['\n', '\t\n', 'quit\n']),
		raising=False,
	)
	radio = CliRadio()
	radio.running = True
	with pytest.raises(ShutdownRequested):
		await radio.run()
	# No crash on empty/whitespace-only lines; still reaches quit.


@pytest.mark.asyncio
async def test_run_shows_hint_when_target_has_no_message(monkeypatch, capsys):
	monkeypatch.setattr(
		cli_radio, 'input', _fake_input(['@4a4fe\n', 'quit\n']),
		raising=False,
	)
	radio = CliRadio()
	radio.running = True
	with pytest.raises(ShutdownRequested):
		await radio.run()
	out = capsys.readouterr().out
	assert '(no message after the target)' in out


if __name__ == '__main__':
	import unittest

	unittest.main()
