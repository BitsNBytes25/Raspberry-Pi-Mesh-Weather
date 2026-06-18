import threading
from collections import deque
import time


class SystemState:
	"""
    The 'Single Source of Truth'.
    Every worker that needs persistent data across threads interacts with this object.
    """
	def __init__(self):
		self.data: dict[str, int | float | str] = {}
		self.history: dict[str, deque] = {}
		self.history_timestamp: dict[str, int] = {}
		# Lock to prevent multiple threads from writing to the dict at the exact same time
		self.lock = threading.Lock()

	def set(self, key: str, value):
		"""
		Set a value in the application state

		:param key:
		:param value:
		:return:
		"""
		with self.lock:
			self.data[key] = value

	def set_with_history(self, key: str, value: int | float):
		"""
		Set a metric value supporting history in the application state

		Metrics behave slightly differently than basic keys, as they retain a 1-hour history too

		:param key:
		:param value:
		:return:
		"""
		with self.lock:
			if key not in self.history:
				# Allow arbitrary values to be stored as new sensors are added.
				self.history[key] = deque(maxlen=60)
				self.history_timestamp[key] = 0

			# Only store 1-minute snapshots for values
			now = int(time.time())
			if self.history_timestamp[key] + 60 <= now:
				self.history[key].append(value)
				self.history_timestamp[key] = now

			# Record the live value too
			self.data[key] = value

	def get(self, key: str, default = None):
		"""
		Get a value from the application state

		:param key:
		:param default:
		:return:
		"""
		with self.lock:
			return self.data.get(key, default)

	def get_all(self) -> dict:
		"""
		Get all values in the application state

		:return:
		"""
		with self.lock:
			return self.data.copy()

	def get_earliest(self, key: str) -> int | float | None:
		"""
		Get the earliest value (up to approximately 1 hour ago), from the history

		:param key:
		:return:
		"""
		with self.lock:
			if key in self.history:
				# Return the first (earliest) value
				return self.history[key][0]
			else:
				# No values stored or metric isn't set yet
				return None

	def get_history(self, key: str) -> list[int | float]:
		"""
		Get the full history (up to approximately 1 hour ago), from the history

		:param key:
		:return:
		"""
		with self.lock:
			if key in self.history:
				return list(self.history[key])
			else:
				return []


# Singleton for the system state
state = SystemState()
