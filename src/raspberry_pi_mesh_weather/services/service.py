import asyncio


class ShutdownRequested(Exception):
    """
    Raised by a service (currently the CLI radio) when it wants the whole
    daemon to shut down.  It is a plain ``Exception`` (not a ``BaseException``)
    so that ``asyncio.gather`` propagates it to the daemon's handler without
    re-raising into the event loop thread (which ``KeyboardInterrupt`` and
    ``SystemExit`` would do).
    """
    pass


class Service:
	def __init__(self):
		self.task = None
		self.running = False

	def get_name(self):
		# self.__class__ refers to the actual class of the instance
		return self.__class__.__name__

	def get_task(self) -> asyncio.Task | None:
		return self.task

	async def load(self) -> bool:
		"""
		Load this service into core system memory and initialize all devices necessary

		If the service could not be loaded for whatever reason, False is returned.

		:return:
		"""
		return False

	async def test(self):
		"""
		Perform any operations useful for manually testing this service
		:return:
		"""
		pass

	async def run(self):
		"""
		Primary runner for this service

		:return:
		"""
		pass

	async def stop(self):
		"""
		Stop this service

		:return:
		"""
		self.running = False

	def start(self) -> asyncio.Task:
		"""
		Start this service and pass a Task object compatible with asyncio

		If the service is already running, the task is returned without starting a second instance

		:return:
		"""
		if self.task is None:
			self.running = True
			self.task = asyncio.create_task(self.run())
		return self.task
