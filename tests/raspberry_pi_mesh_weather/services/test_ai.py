"""
Tests for the sentence-transformer AI command resolver.

The model is replaced with a small mock (`_FakeModel`) that maps phrases to
deterministic unit vectors, so no real model download or torch inference
happens.  Every command's anchors get the command's own direction in the
vector space; a message parallel to that direction scores high against that
command and low against the others.
"""

import math

import numpy as np
import pytest

from raspberry_pi_mesh_weather.libs.commands import command_catalog
from raspberry_pi_mesh_weather.services import ai as ai_module
from raspberry_pi_mesh_weather.services.ai import AiService, get_ai_service, set_ai_service


class _FakeModel:
	"""
	Stand-in for `sentence_transformers.SentenceTransformer`.

	`_vector_table` maps phrase -> vector (a list of floats).  Phrases not in
	the table map to the zero vector.
	"""
	_vector_table = {}

	def __init__(self, model_name_or_path=None, *args, **kwargs):
		self.path = model_name_or_path

	def encode(self, texts, normalize_embeddings=False, **kwargs):
		if isinstance(texts, str):
			texts = [texts]
		return np.stack(
			[np.asarray(_FakeModel._vector_table.get(text, [0.0, 0.0, 0.0])) for text in texts]
		)


class _BreakingModel(_FakeModel):
	def encode(self, *args, **kwargs):
		raise RuntimeError('encode failed')


def _anchor_table():
	"""
	Deterministic 3-D vector table: every command's anchors get the command's
	unit direction on the xy-plane, so a message parallel to one command is
	close to that command and far from all the others.  Messages on the z-axis
	score 0.0 against everything (the "unrelated" case).
	"""
	catalog = command_catalog()
	n = len(catalog)
	table = {}
	for i, entry in enumerate(catalog):
		angle = 2 * math.pi * i / n
		direction = [math.cos(angle), math.sin(angle), 0.0]
		for anchor in entry['anchors']:
			table[anchor] = direction
	return table


def _command_direction(name):
	catalog = command_catalog()
	n = len(catalog)
	index = next(i for i, entry in enumerate(catalog) if entry['name'] == name)
	angle = 2 * math.pi * index / n
	return [math.cos(angle), math.sin(angle), 0.0]


@pytest.fixture
def ai_config(mocker):
	config = mocker.patch.object(ai_module, 'config')
	config.ai.enabled = True
	config.ai.model_path = 'sentence-transformers/test-model'
	config.ai.threshold = 0.5
	return config


@pytest.fixture
def service(ai_config):
	return AiService()


@pytest.fixture
def fake_model(ai_config, mocker):
	mocker.patch.object(ai_module, 'SentenceTransformer', _FakeModel)
	_FakeModel._vector_table = _anchor_table()
	yield None
	_FakeModel._vector_table = {}


@pytest.mark.asyncio
class TestLoad:
	async def test_load_disabled(self, ai_config, service):
		ai_config.enabled = False
		assert await service.load() is False
		assert service.running is False

	async def test_load_requires_model_path(self, ai_config, service):
		ai_config.model_path = ''
		assert await service.load() is False
		assert service.running is False

	async def test_load_missing_package(self, ai_config, service, mocker):
		mocker.patch.object(ai_module, 'SentenceTransformer', None)
		assert await service.load() is False
		assert service.running is False
		assert service._model is None

	async def test_load_model_construction_failure(self, ai_config, service, mocker):
		class _BadModel:
			def __init__(self, model_name_or_path=None):
				raise RuntimeError('bad model')

		mocker.patch.object(ai_module, 'SentenceTransformer', _BadModel)
		assert await service.load() is False
		assert service._model is None
		assert service._embeddings is None

	async def test_load_encode_failure_during_indexing(self, ai_config, service, fake_model, mocker):
		mocker.patch.object(ai_module, 'SentenceTransformer', _BreakingModel)
		assert await service.load() is False
		assert service._model is None
		assert service._embeddings is None

	async def test_load_success_and_indexing(self, ai_config, service, fake_model):
		assert await service.load() is True
		assert service.running is True
		assert service._model is not None
		assert service._model.path == 'sentence-transformers/test-model'
		assert set(service._embeddings) == {entry['name'] for entry in command_catalog()}
		assert service._anchor_count == sum(len(entry['anchors']) for entry in command_catalog())


@pytest.mark.asyncio
class TestStop:
	async def test_stop_clears_state(self, ai_config, service, fake_model):
		await service.load()
		await service.stop()
		assert service.running is False
		assert service._model is None
		assert service._embeddings is None
		assert service.resolve('what is the temperature') is None


class TestResolve:
	def test_resolve_without_load_returns_none(self, ai_config, service):
		assert service.resolve('what is the temperature') is None

	@pytest.mark.asyncio
	async def test_resolves_exact_anchor_phrase(self, ai_config, service, fake_model):
		entry = next(e for e in command_catalog() if e['name'] == 'pressure')
		await service.load()
		assert service.resolve(entry['anchors'][0]) == 'pressure'

	@pytest.mark.asyncio
	async def test_resolves_nearby_phrase(self, ai_config, service, fake_model):
		table = _FakeModel._vector_table
		table['how hot is it'] = [0.9 * x for x in _command_direction('temperature')]
		await service.load()
		assert service.resolve('how hot is it') == 'temperature'

	@pytest.mark.asyncio
	async def test_resolves_distinct_commands_are_distinct(self, ai_config, service, fake_model):
		await service.load()
		for name in ['humidity', 'wind', 'forecast']:
			table_entry = next(e for e in command_catalog() if e['name'] == name)['anchors'][0]
			assert service.resolve(table_entry) == name

	@pytest.mark.asyncio
	async def test_returns_none_when_unrelated(self, ai_config, service, fake_model):
		_FakeModel._vector_table['unrelated phrase'] = [0.0, 0.0, 1.0]
		await service.load()
		assert service.resolve('unrelated phrase') is None

	@pytest.mark.asyncio
	async def test_returns_none_when_below_threshold(self, ai_config, service, fake_model):
		_FakeModel._vector_table['faint phrase'] = [0.4 * x for x in _command_direction('temperature')]
		await service.load()
		assert service.resolve('faint phrase') is None

	@pytest.mark.asyncio
	async def test_resolve_async(self, ai_config, service, fake_model):
		table = _FakeModel._vector_table
		table['how hot is it'] = [0.9 * x for x in _command_direction('temperature')]
		await service.load()
		assert await service.resolve_async('how hot is it') == 'temperature'


class TestSingleton:
	def test_set_and_get(self):
		assert get_ai_service() is None
		svc = AiService()
		set_ai_service(svc)
		assert get_ai_service() is svc
		set_ai_service(None)
		assert get_ai_service() is None
