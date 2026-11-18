"""
Direct-message handling of the MeshCore radio.  These tests verify that
DMs are resolved via `resolve_message` (the AI-capable path) and that the
reply is sent to the sender.

Skipped when the `meshcore` dependency group is not installed.
"""

from unittest.mock import AsyncMock, Mock

import pytest

pytest.importorskip('raspberry_pi_mesh_weather.services.radios.meshcore_radio')

from raspberry_pi_mesh_weather.libs.commands import CommandResponseSuccess
import raspberry_pi_mesh_weather.services.radios.meshcore_radio as meshcore_radio


def _radio_with_sender():
	"""Return a MeshcoreRadio with a stubbed `radio.commands.send_msg`."""
	radio = meshcore_radio.MeshcoreRadio()
	radio.radio = AsyncMock()
	send = AsyncMock(return_value=AsyncMock(type='ok'))
	radio.radio.commands.send_msg = send
	return radio, send


@pytest.mark.asyncio
async def test_meshcore_direct_message_resolved_via_ai_path(mocker):
	radio, send = _radio_with_sender()

	mock_cmd = Mock(return_value=CommandResponseSuccess(message='AI TEST'))
	mocker.patch.object(meshcore_radio, 'resolve_message', return_value=mock_cmd)

	event = Mock()
	event.payload = {'text': 'what is the temperature', 'pubkey_prefix': '!123'}

	await radio.run_direct_message(event)

	send.assert_awaited_once()
	target, message = send.call_args.args
	assert target == '!123'
	assert message == 'AI TEST'
	mock_cmd.assert_called_once_with('!123')


@pytest.mark.asyncio
async def test_meshcore_direct_message_unresolvable_sends_fallback(mocker):
	radio, send = _radio_with_sender()

	mocker.patch.object(meshcore_radio, 'resolve_message', return_value=None)

	event = Mock()
	event.payload = {'text': 'blah blah', 'pubkey_prefix': '!456'}

	await radio.run_direct_message(event)

	send.assert_awaited_once()
	target, message = send.call_args.args
	assert target == '!456'
	assert message == (
		"Sorry, I don't understand that command.  Try \"help\" for a list of commands."
	)


@pytest.mark.asyncio
async def test_meshcore_direct_message_exact_match_path(mocker):
	# The AI-capable resolver is used even for exact matches; this test
	# verifies the exact-match result still flows through the same handler
	# (nothing bypasses resolve_message).
	radio, send = _radio_with_sender()

	mock_cmd = Mock(return_value=CommandResponseSuccess(message='EXACT'))
	mocker.patch.object(meshcore_radio, 'resolve_message', return_value=mock_cmd)

	event = Mock()
	event.payload = {'text': 'temp', 'pubkey_prefix': '!789'}

	await radio.run_direct_message(event)

	send.assert_awaited_once()
	target, message = send.call_args.args
	assert target == '!789'
	assert message == 'EXACT'
	mock_cmd.assert_called_once_with('!789')
