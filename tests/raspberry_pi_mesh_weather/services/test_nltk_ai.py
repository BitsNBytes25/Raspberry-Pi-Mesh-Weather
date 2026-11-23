"""
Tests for the nltk-based lightweight AI command resolver.

The nltk primitives (tokenizer, stopwords) are replaced with deterministic
mocks so no nltk data or network access is required; the real PorterStemmer
and the resolver's own scoring (stemming -> IDF weighting -> cosine) are
exercised end-to-end against the real command catalog.
"""

import re
import sys
from types import SimpleNamespace

import nltk
import pytest

import raspberry_pi_mesh_weather.services.nltk as nltk_ai_module
from raspberry_pi_mesh_weather.libs.commands import command_catalog, get_command, resolve_message
from raspberry_pi_mesh_weather.services.nltk import NltkService
import raspberry_pi_mesh_weather.libs.commands.handler as handler_module

# Stopwords used by the mock `words()` — enough to match the phrases tested
# here; content words such as "temperature" must NOT appear in this list.
_TEST_STOPWORDS = [
	'a', 'about', 'above', 'across', 'after', 'afterwards', 'again', 'against',
	'all', 'almost', 'alone', 'along', 'already', 'also', 'although', 'always',
	'am', 'among', 'amongs', 'amongst', 'an', 'and', 'another', 'any', 'anybody',
	'anyone', 'anything', 'aren', 'are', 'as', 'at', 'audio', 'back', 'be',
	'because', 'before', 'beforehand', 'being', 'below', 'beside', 'besides',
	'between', 'beyond', 'bill', 'both', 'bottom', 'but', 'by', 'call',
	'called', 'came', 'can', 'cant', 'cannot', 'could', 'do', 'does', 'did',
	'doing', 'done', 'don', 'down', 'during', 'each', 'few', 'for', 'from',
	'further', 'had', 'has', 'have', 'having', 'he', 'her', 'hers', 'herself',
	'him', 'himself', 'his', 'how', 'however', 'i', 'if', 'in', 'into', 'is',
	'it', 'its', 'itself', 'just', 'me', 'more', 'most', 'my', 'myself', 'no',
	'nor', 'not', 'now', 'of', 'off', 'on', 'once', 'only', 'or', 'other', 'our',
	'ours', 'ourselves', 'out', 'over', 'own', 'same', 'she', 'should', 'so',
	'some', 'such', 'than', 'that', 'the', 'their', 'theirs', 'them',
	'theirselves', 'then', 'there', 'these', 'they', 'this', 'those',
	'though', 'through', 'three', 'to', 'too', 'under', 'until', 'up', 'upon',
	'very', 'was', 'we', 'were', 'what', 'when', 'where', 'which', 'while',
	'who', 'whom', 'why', 'will', 'with', 'within', 'would', 'you', 'your',
	'yours', 'yourself', 'yourselves',
]


def _mock_word_tokenize(text: str) -> list[str]:
	"""Deterministic stand-in for `nltk.word_tokenize`."""
	return re.findall(r'[a-zA-Z]+', text)


def _mock_words(language: str) -> list[str]:
	return _TEST_STOPWORDS


@pytest.fixture
def nltk_mocks(mocker):
	mocker.patch.object(nltk, 'download', lambda *args, **kwargs: True)
	mocker.patch.object(nltk.tokenize, 'word_tokenize', _mock_word_tokenize)
	# `nltk.corpus.stopwords` is a lazy corpus loader; patch the package
	# attribute with a plain namespace so no data lookup is ever triggered.
	mocker.patch.object(nltk.corpus, 'stopwords', SimpleNamespace(words=_mock_words))
	yield None


@pytest.fixture
def no_nltk_data(mocker):
	"""
	nltk is importable, but its data cannot be obtained (the download is a no-op
	so the probe keeps failing).
	"""
	def _raising_tokenize(text: str):
		raise LookupError('punkt missing')

	mocker.patch.object(nltk, 'download', lambda *args, **kwargs: True)
	mocker.patch.object(nltk.tokenize, 'word_tokenize', _raising_tokenize)
	mocker.patch.object(nltk.corpus, 'stopwords', SimpleNamespace(words=_mock_words))
	yield None


@pytest.fixture
def ai_config(mocker):
	config = mocker.patch.object(nltk_ai_module, 'config')
	config.resolver.enabled = True
	config.resolver.threshold = 0.5
	config.resolver.nltk_threshold = None
	return config


@pytest.fixture
def service(ai_config, nltk_mocks):
	return NltkService()


@pytest.mark.asyncio
class TestLoad:
	async def test_load_disabled(self, ai_config, service, nltk_mocks):
		ai_config.resolver.enabled = False
		assert await service.load() is False
		assert service.running is False

	async def test_load_missing_nltk(self, ai_config, service, mocker):
		mocker.patch.dict(sys.modules, {'nltk': None})
		assert await service.load() is False
		assert service.running is False
		assert service._nltk is None

	async def test_load_unavailable_nltk_data(self, ai_config, service, no_nltk_data):
		assert await service.load() is False
		assert service.running is False

	async def test_load_success_and_indexing(self, ai_config, service, nltk_mocks):
		assert await service.load() is True
		assert service.running is True
		assert service._nltk is not None
		assert service._stopwords is not None
		assert service._idf is not None
		assert set(service._anchor_vectors) == {entry['name'] for entry in command_catalog()}
		assert service._anchor_count == sum(len(entry['anchors']) for entry in command_catalog())
		assert service.resolve in handler_module._message_handlers


@pytest.mark.asyncio
class TestResolve:
	async def test_resolve_without_load_returns_none(self, ai_config, service):
		assert service.resolve('what is the temperature') is None

	@pytest.mark.asyncio
	async def test_resolves_exact_anchor_phrase(self, ai_config, service, nltk_mocks):
		entry = next(e for e in command_catalog() if e['name'] == 'temperature')
		await service.load()
		assert service.resolve(entry['anchors'][0]) is get_command('temperature')

	@pytest.mark.asyncio
	async def test_resolves_paraphrase(self, ai_config, service, nltk_mocks):
		await service.load()
		assert service.resolve('how hot is it') is get_command('temperature')

	@pytest.mark.asyncio
	async def test_resolves_distinct_commands(self, ai_config, service, nltk_mocks):
		await service.load()
		for name, message in (
			('humidity', 'what is the humidity'),
			('pressure', 'give me the current pressure'),
			('forecast', 'what is the weather forecast'),
			('wind', 'how windy is it'),
			('sun', 'what time is sunset'),
			('uptime', 'how long has the device been up'),
			('alerts', 'are there any weather alerts'),
		):
			assert service.resolve(message) is get_command(name), message

	@pytest.mark.asyncio
	async def test_unrelated_returns_none(self, ai_config, service, nltk_mocks):
		await service.load()
		assert service.resolve('i love pizza') is None

	@pytest.mark.asyncio
	async def test_all_stopword_message_matches_raw_anchor(self, ai_config, service, nltk_mocks):
		# "What can you do" is entirely function words, so it goes through
		# the raw-token multiset fallback and must match help's identical
		# anchor — and nothing else.
		await service.load()
		assert service.resolve('what can you do') is get_command('help')
		# A stopword-only message plus a content word falls to the content
		# path; at the default threshold it must not match (e.g. "today"
		# against sun's "today's sunrise").
		ai_config.resolver.nltk_threshold = 0.55
		assert service.resolve('what can you do today') is None

	@pytest.mark.asyncio
	async def test_below_threshold_returns_none(self, ai_config, service, nltk_mocks):
		await service.load()
		# Handcraft the scorer: the message shares "temperat" with the
		# temperature anchor but the anchor has an extra token, fixing the
		# cosine at sqrt(0.5) ~ 0.707 independent of the catalog.
		service._idf = {'temperat': 2.0, 'other': 2.0}
		service._anchor_vectors = {'temperature': [('What is the temperature', {'temperat': 2.0, 'other': 2.0}, [])]}
		service._anchor_count = 1
		ai_config.resolver.nltk_threshold = 0.9
		assert service.resolve('what is the temperature') is None
		ai_config.resolver.nltk_threshold = 0.5
		assert service.resolve('what is the temperature') is get_command('temperature')

	@pytest.mark.asyncio
	async def test_resolve_uses_nltk_threshold_key(self, ai_config, service, nltk_mocks):
		# A message that resolves only under the default threshold must not
		# resolve when nltk_threshold is raised past it.
		await service.load()
		assert service.resolve('give me the current pressure') is get_command('pressure')
		ai_config.resolver.nltk_threshold = 0.9
		assert service.resolve('give me the current pressure') is None

	@pytest.mark.asyncio
	async def test_resolve_async(self, ai_config, service, nltk_mocks):
		await service.load()
		assert await service.resolve_async('how hot is it') is get_command('temperature')


@pytest.mark.asyncio
class TestStop:
	async def test_stop_clears_state(self, ai_config, service, nltk_mocks):
		await service.load()
		await service.stop()
		assert service.running is False
		assert service._nltk is None
		assert service._anchor_vectors is None
		assert service.resolve('how hot is it') is None


@pytest.mark.asyncio
class TestWiring:
	"""
	The resolver registers itself as a message handler, so `resolve_message`
	consults it only after exact name/alias matches.
	"""

	async def test_registered_handler_resolves_via_resolve_message(self, ai_config, service, nltk_mocks):
		await service.load()
		assert resolve_message('how hot is it') is get_command('temperature')

	async def test_exact_match_short_circuits_registered_handler(self, ai_config, service, nltk_mocks):
		await service.load()
		assert resolve_message('temp') is get_command('temperature')

	async def test_registered_handler_unrelated_returns_none(self, ai_config, service, nltk_mocks):
		await service.load()
		assert resolve_message('i love pizza') is None
