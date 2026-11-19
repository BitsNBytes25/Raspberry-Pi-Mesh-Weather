# Raspberry Pi Mesh Weather
#
# https://github.com/BitsNBytes25/Raspberry-Pi-Mesh-Weather
#
# Copyright (c) 2026 Charlie Powell
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://gnu.org>.

import functools
import inspect
import logging
from typing import Callable

from raspberry_pi_mesh_weather.libs.config import config


class CommandResponse:
	"""
	Simple wrapper for command responses,
	useful to know between "" means an error or
	"" means just no data but successful.
	"""
	def __init__(self, success=True, has_data=True, message=None):
		self.success = success
		self.has_data = has_data
		self.message = message


class CommandResponseError(CommandResponse):
	def __init__(self, message=None):
		CommandResponse.__init__(self, False, False, message)


class CommandResponseSuccess(CommandResponse):
	def __init__(self, message=None):
		CommandResponse.__init__(self, True, True, message)


class CommandResponseNoData(CommandResponse):
	def __init__(self, message=None):
		CommandResponse.__init__(self, True, False, message)


_direct_commands = {}
_group_commands = {}
_aliases = {}
_message_handlers = []


def command(
	name: str,
	auth: bool = False,
	direct: bool = False,
	group: bool = False,
	alias: None | str | list[str] = None
):
	"""
	Decorator for commands that can be executed over the mesh

	:param name: String to initiate this command from a mesh message
	:param auth: True/False if command only responds to authenticated devices (default: False)
	:param direct: True/False if command is a DM command (default: False)
	:param group: True/False if command is a #weather channel command (default: False)
	:param alias: Optional list of aliases (or single) to allow running this command with an alias
	:return:
	"""
	def decorator(func):
		@functools.wraps(func)
		def wrapper(pubkey: str | None = None, *args, **kwargs):
			authorized = pubkey is not None and pubkey != '' and pubkey in config.auth_radios
			if auth and not authorized:
				return CommandResponseError(f"You are not authorized to use this command, add {pubkey} to authorize.")
			else:
				return func(*args, **kwargs)

		# Attach the metadata to the wrapped function so the help command can
		# display which commands require authorization.
		wrapper._settings = {
			'auth': auth
		}

		if direct:
			_direct_commands[name] = wrapper

		if group:
			_group_commands[name] = wrapper

		if alias is not None:
			if isinstance(alias, str):
				_aliases[alias] = name
			else:
				for a in alias:
					_aliases[a] = name

		return wrapper
	return decorator


def register_message_handler(handler: Callable[[str], CommandResponse | None]):
	"""
	Register a custom message handler, useful for extended functionality in DMs beyond simple commands

	:param handler:
	:return:
	"""
	_message_handlers.append(handler)


def resolve_cmd_alias(cmd: str) -> str:
	"""
	Resolve a command to its actual cmd while supporting aliases

	If the command requested is not an alias, just the raw cmd is returned instead

	:param cmd:
	:return:
	"""
	if cmd in _aliases:
		return _aliases[cmd]
	return cmd


def get_command(cmd: str) -> Callable[[str | None], CommandResponse] | None:
	"""
	Get the underlying command based on the incoming string name / alias.
	:param cmd:
	:return:
	"""
	cmd = cmd.lower()
	if cmd.startswith('!'):
		# Indicates a group command.
		cmd = resolve_cmd_alias(cmd[1:])
		if cmd in _group_commands:
			return _group_commands[cmd]
		else:
			return None
	else:
		# Lack of '!' indicates a direct command
		cmd = resolve_cmd_alias(cmd)
		if cmd in _direct_commands:
			return _direct_commands[cmd]
		else:
			return None


def command_catalog():
	"""
	Catalog of the direct commands for the AI command resolver.

	Each entry is a dict with:
	  - 'name': the command's registered name
	  - 'aliases': the command's registered aliases
	  - 'anchors': the non-empty lines of the command function's docstring,
	    i.e. the phrasings the AI resolver compares incoming messages against.
	    A command without a docstring falls back to name and aliases only.

	Anchors are derived from the command functions' docstrings (one phrasing
	per line) at call time, so a new command's docstring automatically
	provides its resolver anchors.
	"""
	catalog = []
	for name, wrapper in _direct_commands.items():
		aliases = [a for a, n in _aliases.items() if n == name]
		doc = inspect.getdoc(wrapper)
		anchors = [line.strip() for line in (doc.splitlines() if doc else []) if line.strip()]
		if not anchors:
			logging.warning('command %r has no docstring; AI resolution will fall back to name/alias only', name)
			anchors = [name]
		for alias in aliases:
			if alias not in anchors:
				anchors.append(alias)
		catalog.append({'name': name, 'aliases': aliases, 'anchors': anchors})
	return catalog


def resolve_message(text: str) -> Callable[[str | None], CommandResponse] | None:
	"""
	Resolve direct message text into an executable command.

	An exact command name / alias match always wins. Only if that fails is
	the AI command resolver consulted (in-process sentence transformer, opt-in);
	it can only select from the existing command catalog.

	Note: this performs a blocking model call when the AI is consulted, so
	call it from a worker thread / task (see `AiService.resolve_async` and
	the radio handlers).

	:param text: raw direct message text (radios pass it lower-cased already)
	:return: the command callable to invoke, or None if it cannot be resolved
	"""
	cmd = get_command(text)
	if cmd is not None:
		return cmd
	# Check the extendable handlers
	for handler in _message_handlers:
		cmd = handler(text)
		if cmd is not None:
			return cmd
	return None
