from __future__ import annotations

import json

import pytest
from skiller.infrastructure.llm.config import resolve_llm_settings

pytestmark = pytest.mark.unit

_LLM_ENV_NAMES = (
    "AGENT_LLM_PROVIDER",
    "AGENT_FAKE_LLM_RESPONSE_JSON",
    "AGENT_FAKE_LLM_MODEL",
    "AGENT_MINIMAX_API_KEY",
    "AGENT_MINIMAX_BASE_URL",
    "AGENT_MINIMAX_MODEL",
    "AGENT_MINIMAX_TIMEOUT_SECONDS",
)


def test_resolve_llm_settings_reads_file_and_resolves_provider(tmp_path, monkeypatch) -> None:
    _clear_llm_env(monkeypatch)
    secret_path = tmp_path / "minimax-key"
    secret_path.write_text("secret\n", encoding="utf-8")
    agent_path = tmp_path / "agent.json"
    agent_path.write_text(
        json.dumps(
            {
                "llm": {
                    "default_provider": "minimax-main",
                    "providers": {
                        "minimax-main": {
                            "type": "minimax",
                            "api_key_file": str(secret_path),
                            "base_url": "https://api.minimax.io/v1",
                            "model": "MiniMax-M2.5",
                            "timeout_seconds": 15,
                        }
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    settings = resolve_llm_settings(agent_path)

    assert settings.llm_provider == "minimax"
    assert settings.minimax_api_key == "secret"
    assert settings.minimax_timeout_seconds == 15.0


def test_resolve_llm_settings_prefers_client_type(tmp_path, monkeypatch) -> None:
    _clear_llm_env(monkeypatch)
    agent_path = tmp_path / "agent.json"
    agent_path.write_text(
        json.dumps(
            {
                "llm": {
                    "default_provider": "fake-main",
                    "providers": {
                        "fake-main": {
                            "client_type": "fake",
                            "type": "minimax",
                            "model": "fake-model-v2",
                        }
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    settings = resolve_llm_settings(agent_path)

    assert settings.llm_provider == "fake"
    assert settings.fake_llm_model == "fake-model-v2"


def test_resolve_llm_settings_env_overrides_provider_and_secret(tmp_path, monkeypatch) -> None:
    _clear_llm_env(monkeypatch)
    agent_path = tmp_path / "agent.json"
    agent_path.write_text(
        json.dumps(
            {
                "llm": {
                    "default_provider": "fake-main",
                    "providers": {
                        "fake-main": {"type": "fake"},
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("AGENT_LLM_PROVIDER", "minimax")
    monkeypatch.setenv("AGENT_MINIMAX_API_KEY", "env-key")

    settings = resolve_llm_settings(agent_path)

    assert settings.llm_provider == "minimax"
    assert settings.minimax_api_key == "env-key"


def test_resolve_llm_settings_raises_on_invalid_llm_shape(tmp_path, monkeypatch) -> None:
    _clear_llm_env(monkeypatch)
    agent_path = tmp_path / "agent.json"
    agent_path.write_text(json.dumps({"llm": "invalid"}), encoding="utf-8")

    with pytest.raises(RuntimeError, match="field 'llm' must be a JSON object"):
        resolve_llm_settings(agent_path)


def test_resolve_llm_settings_uses_defaults_when_file_missing(tmp_path, monkeypatch) -> None:
    _clear_llm_env(monkeypatch)
    missing_path = tmp_path / "missing-agent.json"

    settings = resolve_llm_settings(missing_path)

    assert settings.llm_provider == "null"
    assert settings.minimax_base_url == "https://api.minimax.io/v1"


def _clear_llm_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for env_name in _LLM_ENV_NAMES:
        monkeypatch.delenv(env_name, raising=False)
