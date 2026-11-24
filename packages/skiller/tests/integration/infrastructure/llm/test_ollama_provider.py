import importlib.util
import json
from pathlib import Path

import httpx
import pytest
from ollama import Client

from skiller.application.agent.llmodel.llm_model_manager import LLMModelManager
from skiller.application.agent.prompt.prompt_builder import AgentPromptBuilder
from skiller.domain.agent.llm.finish_type import LLMFinishType
from skiller.domain.agent.llm.provider_catalog import LLMAdapterType
from skiller.domain.agent.llm.provider_ollama import OllamaLLMRequest
from skiller.infrastructure.config.file_llm_provider_catalog_datasource import (
    FileLLMProviderCatalogDatasource,
)
from skiller.infrastructure.config.file_llm_provider_catalog_mapper import (
    FileLLMProviderCatalogMapper,
)
from skiller.infrastructure.config.file_llm_provider_catalog_port import FileLLMProviderCatalogPort
from skiller.infrastructure.llm.default_llm_client_resolver import DefaultLLMClientResolver
from skiller.infrastructure.llm.ollama import ollama_llm_port
from skiller.infrastructure.llm.openai.openai_api_key_datasource import OpenAIApiKeyDatasource

pytestmark = pytest.mark.integration


def load_auth():
    spec = importlib.util.spec_from_file_location(
        "ollama_auth", "apps/agents/auths/ollama/ollama_auth.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_catalog(user_path):
    mapper = FileLLMProviderCatalogMapper()
    return FileLLMProviderCatalogPort(
        datasource=FileLLMProviderCatalogDatasource(mapper=mapper),
        mapper=mapper,
        default_path=Path("packages/skiller/src/skiller/application/config/providers.json"),
        user_path=user_path,
        env={},
    ).get_catalog()


def test_auth_catalog_prompt_resolver_and_native_response(tmp_path, monkeypatch):
    auth = load_auth()
    providers_path = tmp_path / "providers.json"
    agent_path = tmp_path / "agent.json"
    monkeypatch.setattr(auth, "providers_file", lambda: providers_path)
    monkeypatch.setattr(auth, "agent_config_file", lambda: agent_path)
    providers_path.write_text(
        json.dumps(
            {
                "providers": {
                    "ollama": {
                        "base_url": "http://ollama.test/v1",
                        "keep_alive": 0,
                        "temperature": 1,
                        "api_key": "ollama",
                        "models": [
                            {
                                "model": "qwen",
                                "context_window_tokens": 4096,
                                "params": {"temperature": 0},
                                "effort_mapping": ["low", "low", "medium", "medium", "xhigh"],
                            }
                        ],
                    }
                }
            }
        )
    )
    original = providers_path.read_text()
    calls = []

    def discovery(endpoint, *, error_message, body=None):
        calls.append(endpoint)
        if endpoint.endswith("/api/tags"):
            return {"models": [{"name": "qwen"}, {"name": "embed"}]}
        if endpoint.endswith("/api/ps"):
            return {"models": [{"name": "qwen", "context_length": 16384}]}
        return {
            "capabilities": ["completion", "thinking", "tools"]
            if body["model"] == "qwen"
            else ["embedding"]
        }

    monkeypatch.setattr(auth, "_request_json", discovery)
    auth.backup_configuration("test-run")
    discovered = auth.configure("http://ollama.test/v1/", "test-run")
    assert discovered["base_url"] == "http://ollama.test"
    assert len(discovered["models"]) == 1
    provider = load_catalog(providers_path).get("ollama")
    assert provider.adapter == LLMAdapterType.OLLAMA
    assert provider.models[0].context_window_tokens == 16384
    assert provider.models[0].params.temperature == 0
    assert json.loads(agent_path.read_text())["llm"]["provider"] == "ollama"
    assert all("/v1/" not in url for url in calls)

    def handler(request):
        assert request.url == "http://ollama.test/api/chat"
        payload = json.loads(request.content)
        assert payload["options"] == {"num_ctx": 16384, "temperature": 0}
        assert payload["think"] == "medium"
        assert payload["keep_alive"] == 0
        assert payload["stream"] is False
        return httpx.Response(
            200,
            json={
                "model": "qwen",
                "done": True,
                "done_reason": "stop",
                "message": {"role": "assistant", "content": "Ready"},
                "prompt_eval_count": 20,
                "eval_count": 5,
                "eval_duration": 1000000,
            },
        )

    monkeypatch.setattr(
        ollama_llm_port,
        "_load_ollama_client_class",
        lambda: lambda **kwargs: Client(**kwargs, transport=httpx.MockTransport(handler)),
    )
    request = AgentPromptBuilder().build_request(
        provider=provider,
        model=provider.models[0],
        system="Be brief",
        entries=[],
        tools=(),
        context_id="test",
        effort=3,
        log_request_file=str(tmp_path / "llm.json"),
        log_override_file=True,
        log_streaming=False,
    )
    assert type(request) is OllamaLLMRequest
    manager = LLMModelManager(
        client_resolver=DefaultLLMClientResolver(
            api_key_datasource=OpenAIApiKeyDatasource(env={}),
        )
    )
    response = manager.generate(provider=provider, request=request)
    assert response.finish_type == LLMFinishType.STOP
    assert response.content == "Ready"
    assert response.usage.provider == "ollama"
    assert response.generation_metrics.output_tokens == 5
    assert json.loads((tmp_path / "llm.json").read_text())["response"]["eval_duration"] == 1000000
    auth.restore_configuration("test-run")
    assert providers_path.read_text() == original
    assert not agent_path.exists()


def test_legacy_provider_url_is_normalized_at_native_transport(monkeypatch):
    provider = load_catalog(None).get("ollama")
    from dataclasses import replace

    monkeypatch.setattr(
        ollama_llm_port, "_load_ollama_client_class", lambda: lambda **kwargs: kwargs
    )
    client = DefaultLLMClientResolver(api_key_datasource=OpenAIApiKeyDatasource(env={})).resolve(
        replace(provider, base_url="http://ollama.test/v1/")
    )
    assert client.client["host"] == "http://ollama.test"


def test_auth_prefers_loaded_model_and_uses_32k_fallback(monkeypatch):
    auth = load_auth()

    def discovery(endpoint, *, error_message, body=None):
        if endpoint.endswith("/api/tags"):
            return {"models": [{"name": "first"}, {"name": "loaded"}]}
        if endpoint.endswith("/api/ps"):
            return {"models": [{"name": "loaded"}]}
        return {"capabilities": ["completion"]}

    monkeypatch.setattr(auth, "_request_json", discovery)
    result = auth.discover_models("http://ollama.test/v1")
    assert result["model"] == "loaded"
    assert all(model["context_window_tokens"] == 32768 for model in result["models"])


def test_auth_routes_validate_and_restore_without_api_key_prompt():
    import yaml

    flow = yaml.safe_load(Path("apps/agents/auths/ollama/ollama.yaml").read_text())
    steps = {step[next(iter(step))]: step for step in flow["steps"]}
    assert steps["route_connection"]["cases"] == {
        "1": "check_ollama_connection",
        "2": "explain_base_url",
        "3": "exit_setup",
    }
    assert steps["write_ollama_config_existing"]["next"] == "verify_ollama"
    assert steps["write_ollama_config_custom"]["next"] == "verify_ollama"
    assert steps["route_ollama_validation"]["default"] == "restore_failed_ollama_config"
    assert "API key" not in json.dumps(flow)


@pytest.fixture
def isolated_auth(tmp_path, monkeypatch):
    auth = load_auth()
    providers = tmp_path / "providers.json"
    agent = tmp_path / "agent.json"
    providers.write_text('{"providers": {}}')
    agent.write_text('{"llm": {"provider": "original"}}')
    monkeypatch.setattr(auth, "providers_file", lambda: providers)
    monkeypatch.setattr(auth, "agent_config_file", lambda: agent)
    monkeypatch.setattr(
        auth,
        "discover_models",
        lambda url: {
            "base_url": url,
            "model": "qwen",
            "models": [{"model": "qwen", "context_window_tokens": 32768}],
        },
    )
    return auth


def test_interrupted_setup_preserves_original_backup_and_blocks_retry(isolated_auth):
    auth = isolated_auth
    original = auth.providers_file().read_text(), auth.agent_config_file().read_text()
    auth.backup_configuration("first")
    auth.configure("http://ollama.test", "first")
    for run_id in ("first", "second"):
        with pytest.raises(ValueError, match="Pending Ollama setup"):
            auth.backup_configuration(run_id)
    for action in (auth.commit_configuration, auth.restore_configuration):
        with pytest.raises(ValueError, match="belongs to run first"):
            action("second")
    with pytest.raises(ValueError, match="belongs to run first"):
        auth.configure("http://other.test", "second")
    auth.restore_configuration("first")
    assert (auth.providers_file().read_text(), auth.agent_config_file().read_text()) == original
    auth.backup_configuration("second")
    auth.commit_configuration("second")
    assert not auth._transaction_directory().exists()


def test_concurrent_backup_attempts_have_one_owner(isolated_auth):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    auth = isolated_auth
    barrier = Barrier(2)

    def attempt(run_id):
        barrier.wait(timeout=5)
        try:
            auth.backup_configuration(run_id)
            return run_id
        except ValueError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        owners = list(pool.map(attempt, ("first", "second")))
    winners = [owner for owner in owners if owner is not None]
    assert len(winners) == 1
    assert (auth._transaction_directory() / "owner").read_text() == winners[0]
    auth.restore_configuration(winners[0])


def test_write_failure_restores_original_configuration(isolated_auth, monkeypatch):
    auth = isolated_auth
    original = auth.providers_file().read_text(), auth.agent_config_file().read_text()
    auth.backup_configuration("first")
    write = auth._write_json_object

    def failing_write(path, payload):
        if path == auth.agent_config_file():
            raise OSError("simulated failure")
        write(path, payload)

    monkeypatch.setattr(auth, "_write_json_object", failing_write)
    with pytest.raises(OSError, match="simulated failure"):
        auth.configure("http://ollama.test", "first")
    assert (auth.providers_file().read_text(), auth.agent_config_file().read_text()) == original
    assert not auth._transaction_directory().exists()


def test_flow_passes_own_run_id_to_all_configuration_operations():
    import yaml

    flow = yaml.safe_load(Path("apps/agents/auths/ollama/ollama.yaml").read_text())
    commands = [step["command"] for step in flow["steps"] if "shell" in step]
    operations = [
        line
        for command in commands
        for line in command.splitlines()
        if 'ollama_auth.py"' in line
        and any(
            f'" {operation}' in line for operation in ("backup", "configure", "commit", "restore")
        )
    ]
    assert len(operations) == 6
    assert all('--run-id "{{flow.run_id}}"' in line for line in operations)


def test_partial_backup_failure_keeps_pending_owner_and_allows_recovery(isolated_auth, monkeypatch):
    auth = isolated_auth
    original = auth.providers_file().read_text(), auth.agent_config_file().read_text()
    copy = auth.shutil.copy2

    def failing_copy(source, target):
        if source == auth.agent_config_file():
            raise OSError("backup interrupted")
        return copy(source, target)

    with monkeypatch.context() as patch:
        patch.setattr(auth.shutil, "copy2", failing_copy)
        with pytest.raises(OSError, match="backup interrupted"):
            auth.backup_configuration("first")
    with pytest.raises(ValueError, match="Pending Ollama setup"):
        auth.backup_configuration("second")
    auth.restore_configuration("first")
    assert (auth.providers_file().read_text(), auth.agent_config_file().read_text()) == original
