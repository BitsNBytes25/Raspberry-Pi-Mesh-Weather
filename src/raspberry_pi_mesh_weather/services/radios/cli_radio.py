# Raspberry Pi Mesh Weather
#
# https://github.com/BitsNBytes25/Raspberry-Pi-Mesh-Weather
#
# Copyright (c) 2026 Charlie Powell
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3.0 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://gnu.org>.

import asyncio
import logging

from raspberry_pi_mesh_weather.libs.config import config
from raspberry_pi_mesh_weather.libs.commands import resolve_message
from raspberry_pi_mesh_weather.services.service import ShutdownRequested, Service

# Fallback text shown when a message cannot be resolved into a command.  Same
# literal the hardware radios send over the mesh (kept in sync with them).
FALLBACK_MESSAGE = (
	"Sorry, I don't understand that command.  "
	'Try "help" for a list of commands.'
)

PROMPT = 'mesh> '


class CliRadio(Service):
	"""
	A hardware-free "radio" used for development.

	Enable it with ``radio.type: "cli"`` and start the daemon.  The radio
	presents an interactive prompt; each line typed is treated as a *direct
	message* (the path the other radios use for DMs) and resolved through
	``resolve_message`` (exact/alias match, then the opt-in AI resolver),
	then executed with the given target.  The reply is printed to the
	terminal.  This lets you exercise the command machinery and the
	scheduled-task ``broadcast()`` output without any attached radio.

	Input syntax
	============
	* ``<message>``                  - direct message using the default target
	* ``@<pubkey> <message>``       - direct message to a specific radio
	* ``?``                         - show this help text
	* ``quit`` / ``exit`` / ``Ctrl-D`` - stop the daemon
	"""

	def __init__(self):
		super().__init__()
		self.weather_channel = 1

	async def load(self) -> bool:
		"""
		No hardware to load.  The prompt is shown from ``run()``.

		:return: ``True`` so the daemon treats the radio as loaded.
		"""
		return True

	async def test(self):
		"""No hardware to test; the prompt is interactive."""
		logging.debug('CLI Radio: ready (no hardware attached)')

	async def run(self):
		self._print_banner()
		loop = asyncio.get_running_loop()

		while self.running:
			try:
				line = await loop.run_in_executor(None, input, PROMPT)
			except EOFError:
				# Ctrl-D / end-of-piped-input: shut the daemon down.
				raise ShutdownRequested
			except asyncio.CancelledError:
				raise  # let the daemon cancel us (real Ctrl-C path)

			text = line.strip().lower()
			if not text:
				continue

			if text == '?':
				self._print_banner()
				continue
			if text in ('quit', 'exit'):
				raise ShutdownRequested

			target, message = self._parse(text)
			if not target:
				# Plain (un-targeted) message: use the default sender target.
				target = self._default_target()
			if not message:
				print('  (no message after the target)')
				continue

			reply = await self._reply(target, message)
			self._print_reply(reply)

	async def broadcast(self, text: str):
		"""
		Print a scheduled-task broadcast to the terminal so it is visible
		alongside the interactive prompt.
		"""
		print()
		print('  [broadcast]')
		for line in str(text).splitlines():
			print('    ' + line)
		print()

	async def stop(self):
		self.running = False

	def _default_target(self) -> str:
		"""
		The pubkey used as the sender for plain (un-targeted) direct
		messages.  Prefers ``radio.target``, then the first entry of
		``auth_radios`` (so authorized commands work by default).
		"""
		target = config.radio.target
		if target:
			return target
		if config.auth_radios:
			return config.auth_radios[0]
		return ''

	@staticmethod
	def _parse(text: str) -> tuple[str, str]:
		"""
		Split an optional leading ``@<pubkey>`` target from the message.

		Both pieces are already lower-cased by the caller.  Returns
	 ``(target, message)``, where ``target`` is empty for plain lines.
		"""
		if text.startswith('@'):
			parts = text[1:].split(None, 1)
			target = parts[0] if parts else ''
			message = parts[1] if len(parts) > 1 else ''
			return target, message
		return '', text

	async def _reply(self, target: str, message: str) -> str:
		"""
		Resolve ``message`` into a command and execute it against ``target``.

		The resolution may call the blocking AI resolver, so it runs on a
		worker thread (matching the hardware radios).  Returns the reply
		message (empty when there is no data).
		"""
		cmd = await asyncio.to_thread(resolve_message, message)
		if cmd is None:
			return FALLBACK_MESSAGE
		response = cmd(target)
		return (response.message or '').strip()

	def _print_banner(self) -> None:
		target = self._default_target()
		print()
		print('CLI Radio — no hardware attached; type messages to simulate the mesh.')
		print(f'  default DM target : {target if target else "(none)"}')
		print('  syntax            : @<pubkey> <message>  -> DM to a specific radio')
		print('                      <message>            -> DM using the default target')
		print('  commands          : ?                  -> show this help')
		print('                      quit / exit        -> stop the daemon  (Ctrl-D too)')
		print()

	def _print_reply(self, reply: str) -> None:
		if reply:
			for line in reply.splitlines():
				print('  ' + line)
		else:
			print('  (no response)')

