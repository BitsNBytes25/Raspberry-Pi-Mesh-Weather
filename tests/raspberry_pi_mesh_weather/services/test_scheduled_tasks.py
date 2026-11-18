from datetime import datetime, timedelta

import asyncio
import unittest.mock as umock

from raspberry_pi_mesh_weather.libs.commands.handler import (
	CommandResponseError,
	CommandResponseNoData,
	CommandResponseSuccess,
)
from raspberry_pi_mesh_weather.services.scheduled_tasks import ScheduledTasks
import raspberry_pi_mesh_weather.services.scheduled_tasks as scheduled_tasks

CMD = 'raspberry_pi_mesh_weather.services.scheduled_tasks.get_command'


class FakeSender:
	"""A stand-in for a radio that records every broadcast."""

	def __init__(self):
		self.sent = []

	async def broadcast(self, text):
		self.sent.append(text)


class FakeClock:
	"""Returns the given datetimes in order, then holds the last one."""

	def __init__(self, datetimes):
		self._datetimes = list(datetimes)
		self._index = 0

	def __call__(self):
		if self._index < len(self._datetimes):
			dt = self._datetimes[self._index]
			self._index += 1
		else:
			dt = self._datetimes[-1]
		return dt


def patch_command(mocker, response):
	# Every command resolves to the same response.
	mocker.patch(CMD, return_value=lambda name: response)


def patch_command_by_name(mocker, responses):
	"""
	Patch get_command so each task gets its own response.

	get_command(name) must return either None or a callable (target) ->
	CommandResponse.  `responses` maps the underlying command name to a
	 single response or a per-call sequence, keyed by 'forecast', 'all'
	 and 'alerts'.
	"""
	sequences = {name: list(seq) for name, seq in responses.items()}
	index = {name: 0 for name in responses}

	def fake(name):
		key = name.lower().lstrip('!')

		def cmd(target):
			resp = sequences[key][index[key]]
			index[key] += 1
			return resp

		return cmd

	mocker.patch(CMD, side_effect=fake)


def patch_new_alerts(mocker, sequences, label='cbus'):
	"""
	Patch scheduled_tasks.get_new_alerts to return the per-call sequence in
	`sequences` (holding the last value once exhausted), raising if an entry
	is an Exception instance.  Pin a valid location in config so run_alerts
	proceeds to the fetch/broadcast path.
	"""
	sequences = list(sequences)
	index = 0

	def side_effect(lat, lon):
		nonlocal index
		value = sequences[index] if index < len(sequences) else sequences[-1]
		index += 1
		if isinstance(value, Exception):
			raise value
		return value

	mocker.patch.object(scheduled_tasks, 'get_new_alerts', side_effect=side_effect)
	config = mocker.patch.object(scheduled_tasks, 'config')
	config.location.lat = 33.47
	config.location.lon = -87.44
	config.location.label = label
	return config


def run_loop(service, max_iters):
	"""
	Run the service loop for exactly `max_iters` iterations using a patched
	`asyncio.sleep` so the loop is deterministic and finishes immediately.
	"""
	service.running = True
	calls = 0
	real_sleep = asyncio.sleep  # capture before patching to avoid recursion

	def fake_sleep(_seconds):
		nonlocal calls
		calls += 1
		if calls >= max_iters:
			service.running = False
		return real_sleep(0)

	with umock.patch('asyncio.sleep', fake_sleep):
		asyncio.run(service.run())


# --- run_daily_forecast ---------------------------------------------------


def test_run_daily_forecast_success_broadcasts(mocker):
	sender = FakeSender()
	svc = ScheduledTasks(sender)
	patch_command(mocker, CommandResponseSuccess(message='Forecast: sunny'))

	result = asyncio.run(svc.run_daily_forecast())

	assert sender.sent == ['Forecast: sunny']
	assert result is True


def test_run_daily_forecast_command_missing_does_not_broadcast(mocker):
	sender = FakeSender()
	svc = ScheduledTasks(sender)
	mocker.patch(CMD, return_value=None)

	result = asyncio.run(svc.run_daily_forecast())

	assert sender.sent == []


def test_run_daily_forecast_failure_does_not_broadcast(mocker):
	sender = FakeSender()
	svc = ScheduledTasks(sender)
	patch_command(mocker, CommandResponseError('open weather map down'))

	result = asyncio.run(svc.run_daily_forecast())

	assert sender.sent == []


def test_run_daily_forecast_no_data_does_not_broadcast(mocker):
	sender = FakeSender()
	svc = ScheduledTasks(sender)
	patch_command(mocker, CommandResponseNoData())

	result = asyncio.run(svc.run_daily_forecast())

	assert sender.sent == []


# --- run_alerts ------------------------------------------------------------


def test_run_alerts_success_broadcasts(mocker):
	sender = FakeSender()
	svc = ScheduledTasks(sender)
	patch_new_alerts(mocker, [[{'icon': 'ALERT', 'title': 'Tornado Warning'}]])

	result = asyncio.run(svc.run_alerts())

	assert result is True
	assert sender.sent == ['ALERT  Tornado Warning']


def test_run_alerts_missing_location_does_not_broadcast(mocker):
	sender = FakeSender()
	svc = ScheduledTasks(sender)
	config = mocker.patch.object(scheduled_tasks, 'config')
	config.location.lat = None
	config.location.lon = -87.44

	result = asyncio.run(svc.run_alerts())

	assert result is False
	assert sender.sent == []


def test_run_alerts_failure_does_not_broadcast(mocker):
	sender = FakeSender()
	svc = ScheduledTasks(sender)
	patch_command(mocker, CommandResponseError('api down'))

	result = asyncio.run(svc.run_alerts())

	assert result is False
	assert sender.sent == []


def test_run_alerts_no_data_does_not_broadcast(mocker):
	sender = FakeSender()
	svc = ScheduledTasks(sender)
	patch_new_alerts(mocker, [[]])

	result = asyncio.run(svc.run_alerts())

	assert result is False
	assert sender.sent == []


def test_run_alerts_gates_repeat_checks_within_interval(mocker):
	sender = FakeSender()
	svc = ScheduledTasks(sender)
	patch_new_alerts(mocker, [[{'icon': 'ALERT', 'title': 'Tornado Warning'}]])

	asyncio.run(svc.run_alerts())
	# Second check in the same tick is within the 5-minute window.
	asyncio.run(svc.run_alerts())

	assert sender.sent == ['ALERT  Tornado Warning']


def test_run_alerts_runs_again_after_interval(mocker):
	sender = FakeSender()
	svc = ScheduledTasks(sender)
	patch_new_alerts(mocker, [[{'icon': 'ALERT', 'title': 'Tornado Warning'}]])

	asyncio.run(svc.run_alerts())
	# Advance the tick clock past the 5-minute window.
	svc._current_timestamp += ScheduledTasks.ALERT_INTERVAL
	asyncio.run(svc.run_alerts())

	assert sender.sent == [
		'ALERT  Tornado Warning',
		'ALERT  Tornado Warning',
	]


# --- load / test ----------------------------------------------------------


def test_load_returns_true():
	assert asyncio.run(ScheduledTasks(FakeSender()).load()) is True


# --- run loop -------------------------------------------------------------


def test_run_forecast_and_current_broadcast_in_their_windows(mocker):
	sender = FakeSender()
	base = datetime(2026, 11, 14)
	clock = FakeClock([
		base + timedelta(hours=7),
		base + timedelta(hours=7, minutes=1),
		base + timedelta(hours=12),
		base + timedelta(hours=12, minutes=1),
	])
	svc = ScheduledTasks(sender, clock=clock)
	patch_command_by_name(mocker, {
		'forecast': [CommandResponseSuccess(message='F')],
		'all': [CommandResponseSuccess(message='W')],
	})
	patch_new_alerts(mocker, [[], [], [], []])

	run_loop(svc, 4)

	# 7 AM forecast plus the daytime current-weather broadcast at 12 PM.
	assert sender.sent == ['F', 'W']


def test_run_alert_preempts_forecast_same_tick(mocker):
	sender = FakeSender()
	base = datetime(2026, 11, 14)
	clock = FakeClock([
		base + timedelta(hours=7),
	])
	svc = ScheduledTasks(sender, clock=clock)
	patch_command_by_name(mocker, {
		'forecast': [CommandResponseSuccess(message='F')],
	})
	patch_new_alerts(mocker, [[{'icon': 'ALERT', 'title': 'Tornado Warning'}]])

	run_loop(svc, 1)

	# The alert takes this tick's broadcast slot; the in-window forecast
	# is skipped.
	assert sender.sent == ['ALERT  Tornado Warning']


def test_run_alert_preempts_current_weather_same_tick(mocker):
	sender = FakeSender()
	base = datetime(2026, 11, 14)
	clock = FakeClock([
		base + timedelta(hours=12),
	])
	svc = ScheduledTasks(sender, clock=clock)
	patch_command_by_name(mocker, {
		'all': [CommandResponseSuccess(message='W')],
	})
	patch_new_alerts(mocker, [[{'icon': 'ALERT', 'title': 'Tornado Warning'}]])

	run_loop(svc, 1)

	# The alert takes this tick's broadcast slot; current weather is skipped.
	assert sender.sent == ['ALERT  Tornado Warning']


def test_run_forecast_still_runs_when_no_alert_sent(mocker):
	sender = FakeSender()
	base = datetime(2026, 11, 14)
	clock = FakeClock([
		base + timedelta(hours=7),
	])
	svc = ScheduledTasks(sender, clock=clock)
	patch_command_by_name(mocker, {
		'forecast': [CommandResponseSuccess(message='F')],
	})
	patch_new_alerts(mocker, [[]])

	run_loop(svc, 1)

	# No alert broadcast, so the in-window forecast still goes out.
	assert sender.sent == ['F']


def test_run_retries_after_failure(mocker):
	sender = FakeSender()
	base = datetime(2026, 11, 14)
	clock = FakeClock([
		base + timedelta(hours=7),
		base + timedelta(hours=7, minutes=1),
	])
	svc = ScheduledTasks(sender, clock=clock)
	patch_command_by_name(mocker, {
		'forecast': [
			CommandResponseError('open weather map down'),
			CommandResponseSuccess(message='F'),
		],
	})
	patch_new_alerts(mocker, [[], []])

	run_loop(svc, 2)

	# Only the successful second attempt is broadcast.
	assert sender.sent == ['F']


def test_run_alert_retries_next_due_tick(mocker):
	sender = FakeSender()
	base = datetime(2026, 11, 14)
	clock = FakeClock([
		base + timedelta(hours=7),
		base + timedelta(hours=7, minutes=6),
	])
	svc = ScheduledTasks(sender, clock=clock)
	patch_command_by_name(mocker, {
		'forecast': [CommandResponseNoData()],
	})
	patch_new_alerts(mocker, [[], [{'icon': 'ALERT', 'title': 'Tornado Warning'}]])

	run_loop(svc, 2)

	# Tick one alert fails and nothing else is sent; the retry on the next
	# due tick (past the 5-minute window) succeeds.
	assert sender.sent == ['ALERT  Tornado Warning']


if __name__ == '__main__':
	import unittest
	unittest.main()
