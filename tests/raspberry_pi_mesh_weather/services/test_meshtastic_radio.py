"""
Direct-message handling of the Meshtastic radio.  These tests verify that
DMs are resolved via `resolve_message` (the AI-capable path) and that the
reply is sent to the sender node.

Skipped when the `meshtastic` dependency group is not installed.
"""

import asyncio
from unittest.mock import Mock

import pytest

pytest.importorskip('raspberry_pi_mesh_weather.services.radios.meshtastic_radio')

from raspberry_pi_mesh_weather.libs.commands import CommandResponseSuccess
import raspberry_pi_mesh_weather.services.radios.meshtastic_radio as meshtastic_radio


def _packet(text: str, to: int, from_id: int) -> dict:
	return {
		'to': to,
		'from': from_id,
		'decoded': {'text': text},
	}


@pytest.mark.asyncio
def test_meshtastic_direct_message_resolved_via_ai_path(mocker):
	radio = meshtastic_radio.MeshtasticRadio()
	interface = Mock()
	interface.localNode.nodeNum = 1
	interface.sendText = Mock()

	mock_cmd = Mock(return_value=CommandResponseSuccess(message='AI TEST'))
	mocker.patch.object(meshtastic_radio, 'resolve_message', return_value=mock_cmd)

	radio.run_direct_message(_packet('what is the temperature', to=1, from_id=123), interface)

	interface.sendText.assert_called_once()
	kwargs = interface.sendText.call_args[1]
	assert kwargs['destinationId'] == '!0000007b'
	assert kwargs['text'] == 'AI TEST'
	mock_cmd.assert_called_once_with('!0000007b')


@pytest.mark.asyncio
def test_meshtastic_direct_message_unresolvable_sends_fallback(mocker):
	radio = meshtastic_radio.MeshtasticRadio()
	interface = Mock()
	interface.localNode.nodeNum = 1
	interface.sendText = Mock()

	mocker.patch.object(meshtastic_radio, 'resolve_message', return_value=None)

	radio.run_direct_message(_packet('blah blah', to=1, from_id=123), interface)

	interface.sendText.assert_called_once()
	kwargs = interface.sendText.call_args[1]
	assert kwargs['destinationId'] == '!0000007b'
	assert kwargs['text'] == (
		"Sorry, I don't understand that command.  Try \"help\" for a list of commands."
	)


@pytest.mark.asyncio
def test_meshtastic_direct_message_exact_match_path(mocker):
	radio = meshtastic_radio.MeshtasticRadio()
	interface = Mock()
	interface.localNode.nodeNum = 1
	interface.sendText = Mock()

	mock_cmd = Mock(return_value=CommandResponseSuccess(message='EXACT'))
	mocker.patch.object(meshtastic_radio, 'resolve_message', return_value=mock_cmd)

	radio.run_direct_message(_packet('temp', to=1, from_id=123), interface)

	interface.sendText.assert_called_once()
	mock_cmd.assert_called_once_with('!0000007b')
