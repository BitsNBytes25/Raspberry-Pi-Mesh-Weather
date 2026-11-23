# Raspberry Pi Mesh Weather
#
# https://github.com/BitsNBytes25/Raspberry-Pi-Mesh-Weather
#
# Copyright (c) 2026 Charlie Powell
#
# This program is free software: you can redistribute and/or modify
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
# along with the program.  If not, see <https://gnu.org>.

import asyncio
import logging
import math
from collections import Counter
from typing import Callable

import nltk
import psutil
from nltk.stem.porter import PorterStemmer

from raspberry_pi_mesh_weather.libs.config import config
from raspberry_pi_mesh_weather.libs.commands import command_catalog, CommandResponse
from raspberry_pi_mesh_weather.libs.commands.handler import register_message_handler, get_command
from raspberry_pi_mesh_weather.services.service import Service


class NltkService(Service):
	"""
	Lightweight nltk-based local command resolver (alternative for low-RAM devices).

	Classifies unrecognized direct messages into a known command using the same
	command catalog anchors as the sentence-transformer resolver
	(`services/ai.py`) — each command function's docstring lines, plus its
	registered aliases — but without the model runtime: text is tokenized,
	stemmed, filtered for stopwords and weighted by TF-IDF, then scored by
	cosine similarity against the pre-built anchor vectors (see
	`_index_anchors`).  Replies are always produced by the normal commands and
	exact command/alias matches are handled before this service is consulted
	(see `resolve_message` in `libs/commands/handler.py`).  If nltk or its data
	are unavailable, or no anchor is close enough (`ai.nltk_threshold`, defaulting
	to `ai.threshold`), resolution yields None and the existing "I don't
	understand that command" response is sent.

	Footprint is a few hundred KB of nltk data and only a few MB of RAM, so it
	runs on low-memory Pis where torch cannot fit.  The daemon selects it as a
	fallback when the transformer resolver cannot load (see
	`_load_ai_service` in `daemon.py`).
	"""

	def __init__(self):
		super().__init__()
		self._nltk = None
		self._stopwords: set[str] | None = None
		self._stemmer: PorterStemmer | None = None
		self._idf: dict[str, float] | None = None
		self._anchor_vectors: dict[str, list[tuple[str, dict[str, float], list[str]]]] | None = None
		self._anchor_count = 0

	def get_name(self):
		return 'Command Resolver (nltk)'

	def _index_anchors(self) -> int:
		"""
		Build a TF-IDF vector for every command anchor and cache them per
		command.

		Anchors are the non-empty lines of each command function's docstring,
		plus its registered aliases (see `command_catalog`).  Each vector is a
		`dict` mapping stemmed content tokens to TF-IDF weights, stored alongside
		the anchor text and its lower-case raw tokens (used by the raw multiset
		fallback in `resolve`).

		:return: number of anchors indexed, or 0 when there is nothing to index.
		"""
		catalog = command_catalog()
		texts = [anchor for entry in catalog for anchor in entry['anchors']]
		if not texts:
			return 0

		# Document frequency over all command anchors, for IDF weighting.
		doc_count: Counter = Counter()
		raw_lists: list[list[str]] = []
		content_lists: list[list[str]] = []
		for text in texts:
			raw_tokens = [w.lower() for w in nltk.tokenize.word_tokenize(text)]
			content_tokens = [self._stemmer.stem(w) for w in raw_tokens if w not in self._stopwords]
			doc_count.update(set(content_tokens))
			raw_lists.append(raw_tokens)
			content_lists.append(content_tokens)

		self._idf = {term: math.log1p(len(texts) / df) for term, df in doc_count.items()}

		vectors: dict[str, list[tuple[str, dict[str, float], list[str]]]] = {}
		offset = 0
		for entry in catalog:
			per_command: list[tuple[str, dict[str, float], list[str]]] = []
			for anchor in entry['anchors']:
				content_tokens = content_lists[offset]
				raw_tokens = raw_lists[offset]
				offset += 1
				weights: dict[str, float] = {}
				for stem, count in Counter(content_tokens).items():
					weights[stem] = self._idf[stem] * count
				per_command.append((anchor, weights, raw_tokens))
			vectors[entry['name']] = per_command

		self._anchor_vectors = vectors
		self._anchor_count = len(texts)
		return self._anchor_count

	async def load(self) -> bool:
		if not config.resolver.enabled:
			logging.info('nltk command resolver disabled')
			return False

		try:
			# Ensure the nltk data is available; the download is a no-op when the
			# data is already present.
			nltk.download('punkt', quiet=True)
			nltk.download('punkt_tab', quiet=True)
			nltk.download('stopwords', quiet=True)
			# Probe that tokenization and the stopwords corpus actually load.
			nltk.tokenize.word_tokenize('hello world')
			self._stopwords = set(nltk.corpus.stopwords.words('english'))
			self._stemmer = PorterStemmer()
		except Exception as e:
			self._nltk = None
			logging.error('nltk command resolver could not load nltk data: %s', e)
			return False

		self._nltk = nltk

		indexed = self._index_anchors()
		if not indexed:
			logging.error('nltk command resolver could not index command anchors; not loaded')
			return False

		# Load the nltk resolver into the message handlers
		register_message_handler(self.resolve)

		self.running = True
		logging.info(
			'nltk command resolver ready (%d anchors indexed across %d commands)',
			self._anchor_count, len(self._anchor_vectors)
		)
		return True

	def resolve(self, text: str) -> Callable[[str | None], CommandResponse] | None:
		"""
		Map `text` onto a command by scoring it against the cached anchor vectors.

		Content tokens (non-stopword stems) are compared per anchor with cosine
		similarity; the best-scoring anchor per command is considered, and the
		command with the overall highest score is returned when that score
		reaches `ai.nltk_threshold` (defaulting to `ai.threshold`).  Messages
		with no content tokens (e.g. "what can you do") fall back to an exact
		token multiset match against an anchor.

		:return: the best-matching command when its closest anchor score is at or
			above the threshold, else None (service not loaded, empty message,
			or nothing close enough).
		"""
		if self._nltk is None or self._anchor_vectors is None:
			return None
		if not text or not text.strip():
			return None

		try:
			raw_tokens = [w.lower() for w in nltk.tokenize.word_tokenize(text)]
			content_tokens = [
				self._stemmer.stem(w) for w in raw_tokens if w not in self._stopwords
			]
		except Exception as e:
			logging.warning('nltk command resolver failed to process %r: %s', text, e)
			return None

		best_name: str | None = None
		best_score = -1.0

		if content_tokens:
			message_weights: dict[str, float] = {}
			for stem, count in Counter(content_tokens).items():
				message_weights[stem] = self._idf.get(stem, 1.0) * count
			message_norm = math.sqrt(sum(w * w for w in message_weights.values()))
			for name, anchors in self._anchor_vectors.items():
				for _, anchor_weights, _ in anchors:
					dot = sum(
						weight * anchor_weights.get(term, 0.0)
						for term, weight in message_weights.items()
					)
					if dot <= 0.0:
						continue
					anchor_norm = math.sqrt(sum(w * w for w in anchor_weights.values()))
					score = dot / (message_norm * anchor_norm)
					if score > best_score:
						best_score, best_name = score, name
		else:
			# No content tokens: fall back to an exact raw-token multiset match
			# against an anchor.
			message_tokens = Counter(raw_tokens)
			for name, anchors in self._anchor_vectors.items():
				for _, _, anchor_raw in anchors:
					if Counter(anchor_raw) == message_tokens:
						best_name, best_score = name, 1.0
						break
				if best_name is not None:
					break

		if best_name is None:
			return None

		threshold = (
			config.resolver.nltk_threshold
			if config.resolver.nltk_threshold is not None
			else config.resolver.threshold
		)
		if best_score >= threshold:
			return get_command(str(best_name))
		return None

	async def resolve_async(self, text: str) -> str | None:
		# Worker-thread resolution so the daemon's event loop is never
		# blocked by the (potentially slow) tokenization/scoring pass.
		return await asyncio.to_thread(self.resolve, text)

	async def stop(self):
		# Drop references to free the resolver's memory on a Pi.
		self._nltk = None
		self._stopwords = None
		self._stemmer = None
		self._idf = None
		self._anchor_vectors = None
		self._anchor_count = 0
		self.running = False

	async def test(self):
		cmd = self.resolve('what is the temperature')
		print(
			f'nltk command resolver: {self._anchor_count} anchors indexed; '
			f'sample resolve ("what is the temperature") -> {getattr(cmd, "__name__", None)}'
		)
