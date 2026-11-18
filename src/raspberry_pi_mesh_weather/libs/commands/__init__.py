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

# Common command handling (registry, dispatch, response types).
from .handler import (
	CommandResponse,
	CommandResponseError,
	CommandResponseNoData,
	CommandResponseSuccess,
	command,
	command_catalog,
	get_command,
	resolve_message,
)

# Individual commands.  Importing each module registers its command(s)
# with the handler's direct/group registries.
from .alerts import cmd_alerts
from .about import cmd_about
from .all_sensors import cmd_all_sensors
from .cpu import cmd_cpu
from .forecast import cmd_daily_forecast
from .help import cmd_direct_help, cmd_group_help
from .icons import cmd_icons
from .humidity import cmd_humidity
from .net import cmd_net
from .ping import cmd_ping
from .pres import cmd_pressure
from .reboot import cmd_reboot
from .sun import cmd_sun
from .temp import cmd_temp, get_heat_index
from .uptime import cmd_uptime
from .wake import cmd_wake
from .wind import cmd_wind
