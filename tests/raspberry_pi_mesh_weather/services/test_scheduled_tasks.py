from datetime import datetime, timedelta

import asyncio
import unittest.mock as umock

from raspberry_pi_mesh_weather.libs.commands.handler import (
	CommandResponseError,
	CommandResponseNoData,
	CommandResponseSuccess,
)
from raspberry_pi_mesh_weather.services.scheduled_tasks import ScheduledTasks

FORECAST_CMD = 'raspberry_pi_mesh_weather.services.scheduled_tasks.get_command'


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
	mocker.patch(FORECAST_CMD, return_value=lambda target: response)


def patch_command_sequence(mocker, *responses):
	index = 0

	def cmd(target):
		nonlocal index
		resp = responses[index]
		index += 1
		return resp

	mocker.patch(FORECAST_CMD, return_value=cmd)


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


def test_run_daily_forecast_command_missing_does_not_broadcast(mocker):
	sender = FakeSender()
	svc = ScheduledTasks(sender)
	mocker.patch(FORECAST_CMD, return_value=None)

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


# --- load / test ----------------------------------------------------------


def test_load_returns_true():
	assert asyncio.run(ScheduledTasks(FakeSender()).load()) is True


# --- run loop -------------------------------------------------------------


def test_run_sends_when_due_and_stays_silent_when_not(mocker):
	sender = FakeSender()
	base = datetime(2026, 11, 14)
	clock = FakeClock([
		base + timedelta(hours=7),           # in window, due -> send
		base + timedelta(hours=7, minutes=1),  # in window, too soon -> skip
		base + timedelta(hours=12),          # out of window -> skip
		base + timedelta(hours=12, minutes=1), # out of window -> skip
	])
	svc = ScheduledTasks(sender, clock=clock)
	patch_command(mocker, CommandResponseSuccess(message='F'))

	run_loop(svc, 4)

	assert sender.sent == ['F']


def test_run_retries_after_failure(mocker):
	sender = FakeSender()
	base = datetime(2026, 11, 14)
	clock = FakeClock([
		base + timedelta(hours=7),
		base + timedelta(hours=7, minutes=1),
	])
	svc = ScheduledTasks(sender, clock=clock)
	patch_command_sequence(
		mocker,
		CommandResponseError('down'),
		CommandResponseSuccess(message='F'),
	)

	run_loop(svc, 2)

	# Only the successful second attempt is broadcast.
	assert sender.sent == ['F']
