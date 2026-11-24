"""
Tests for daemon AI backend selection (`_ai_backends`) and fallback loading
(`_load_ai_service`).
"""

import pytest

import raspberry_pi_mesh_weather.daemon as daemon_module


@pytest.fixture
def ai_enabled_config(mocker):
	config = mocker.patch.object(daemon_module, 'config')
	config.resolver.enabled = True
	return config


@pytest.mark.asyncio
class TestLoadAiService:
	@pytest.mark.asyncio
	async def test_transformer_loads_first(self, ai_enabled_config, mocker):
		ai_svc = object()
		nltk_svc = object()
		calls = []

		def fake_load_service(name, *args, **kwargs):
			calls.append(name)
			return (ai_svc, True) if name == 'ai' else (nltk_svc, True)

		mocker.patch.object(daemon_module, '_load_service', fake_load_service)
		service, loadable = await daemon_module._load_ai_service()
		assert service is ai_svc
		assert loadable
		assert calls == ['ai']

	@pytest.mark.asyncio
	async def test_transformer_fails_falls_back_to_nltk(self, ai_enabled_config, mocker):
		ai_svc = object()
		nltk_svc = object()
		calls = []

		def fake_load_service(name, *args, **kwargs):
			calls.append(name)
			if name == 'ai':
				return None, False
			return nltk_svc, True

		mocker.patch.object(daemon_module, '_load_service', fake_load_service)
		service, loadable = await daemon_module._load_ai_service()
		assert service is nltk_svc
		assert loadable
		assert calls == ['ai', 'ai_nltk']

	@pytest.mark.asyncio
	async def test_both_backends_fail(self, ai_enabled_config, mocker):
		calls = []

		def fake_load_service(name, *args, **kwargs):
			calls.append(name)
			return None, False

		mocker.patch.object(daemon_module, '_load_service', fake_load_service)
		service, loadable = await daemon_module._load_ai_service()
		assert service is None
		assert not loadable
		assert calls == ['ai', 'ai_nltk']

	@pytest.mark.asyncio
	async def test_nltk_backend_skips_transformer(self, ai_enabled_config, mocker):
		ai_svc = object()
		nltk_svc = object()
		calls = []
		ai_enabled_config.backend = 'nltk'

		def fake_load_service(name, *args, **kwargs):
			calls.append(name)
			return (ai_svc, True) if name == 'ai' else (nltk_svc, True)

		mocker.patch.object(daemon_module, '_load_service', fake_load_service)
		service, loadable = await daemon_module._load_ai_service()
		assert service is nltk_svc
		assert loadable
		assert calls == ['ai_nltk']

	@pytest.mark.asyncio
	async def test_transformer_backend_skips_fallback(self, ai_enabled_config, mocker):
		ai_svc = object()
		nltk_svc = object()
		calls = []
		ai_enabled_config.backend = 'transformer'

		def fake_load_service(name, *args, **kwargs):
			calls.append(name)
			return None, False

		mocker.patch.object(daemon_module, '_load_service', fake_load_service)
		service, loadable = await daemon_module._load_ai_service()
		assert service is None
		assert not loadable
		assert calls == ['ai']

	@pytest.mark.asyncio
	async def test_ai_disabled_returns_none_without_loading(self, mocker):
		config = mocker.patch.object(daemon_module, 'config')
		config.resolver.enabled = False
		config.resolver.backend = 'auto'
		calls = []
		def fake_load_service(name, *args, **kwargs):
			calls.append(name)
			return None, False

		mocker.patch.object(daemon_module, '_load_service', fake_load_service)
		service, loadable = await daemon_module._load_ai_service()
		assert service is None
		assert not loadable
		assert calls == []


class TestAiBackends:
	def test_auto_returns_both(self, mocker):
		config = mocker.patch.object(daemon_module, 'config')
		config.resolver.enabled = True
		config.resolver.backend = 'auto'
		assert daemon_module._ai_backends() == ('ai', 'ai_nltk')

	def test_transformer_returns_ai_only(self, mocker):
		config = mocker.patch.object(daemon_module, 'config')
		config.resolver.enabled = True
		config.resolver.backend = 'transformer'
		assert daemon_module._ai_backends() == ('ai',)

	def test_nltk_returns_nltk_only(self, mocker):
		config = mocker.patch.object(daemon_module, 'config')
		config.resolver.enabled = True
		config.resolver.backend = 'nltk'
		assert daemon_module._ai_backends() == ('ai_nltk',)

	def test_disabled_returns_empty(self, mocker):
		config = mocker.patch.object(daemon_module, 'config')
		config.resolver.enabled = False
		assert daemon_module._ai_backends() == ()

	def test_unknown_backend_falls_back_to_auto(self, mocker):
		config = mocker.patch.object(daemon_module, 'config')
		config.resolver.enabled = True
		config.resolver.backend = 'bogus'
		assert daemon_module._ai_backends() == ('ai', 'ai_nltk')
