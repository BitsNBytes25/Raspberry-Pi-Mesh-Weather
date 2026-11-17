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

from .handler import command, CommandResponse, CommandResponseSuccess, _direct_commands, _group_commands


@command('help', direct=True)
def cmd_direct_help(target: str | None = None) -> CommandResponse:
	message = ''
	commands = []
	for cmd in _direct_commands.keys():
		if _direct_commands[cmd]._settings['auth']:
			commands.append(' '.join([cmd, '🔒']))
		else:
			commands.append(cmd)
	message += ' | '.join(commands)

	return CommandResponseSuccess(message)


@command('help', group=True)
def cmd_group_help(target: str | None = None) -> CommandResponse:
	message = ''
	commands = _group_commands.keys()
	message += '!' + ' | !'.join(commands)

	return CommandResponseSuccess(message)
