from __future__ import annotations

import pytest

from skiller.infrastructure.config import settings as settings_module

pytestmark = pytest.mark.unit


def test_get_settings_loads_dotenv_once_without_overriding_env(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text(
        (
            "AGENT_DB_PATH=./runtime.from.dotenv.db\n"
            "AGENT_LLM_PROVIDER=fake\n"
            "AGENT_FAKE_LLM_MODEL=dotenv-model\n"
            "export AGENT_WEBHOOKS_PORT=9001\n"
        ),
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("AGENT_DB_PATH", raising=False)
    monkeypatch.setenv("AGENT_LLM_PROVIDER", "minimax")
    monkeypatch.setattr(settings_module, "_DOTENV_LOADED", False)

    settings = settings_module.get_settings()

    assert settings.db_path == "./runtime.from.dotenv.db"
    assert settings.llm_provider == "minimax"
    assert settings.fake_llm_model == "dotenv-model"
    assert settings.webhooks_port == 9001


def test_get_settings_ignores_missing_dotenv(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("AGENT_DB_PATH", raising=False)
    monkeypatch.setattr(settings_module, "_DOTENV_LOADED", False)

    settings = settings_module.get_settings()

    assert settings.db_path == "./runtime.db"


def test_get_settings_does_not_reload_after_first_call(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text("AGENT_LLM_PROVIDER=fake\n", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("AGENT_LLM_PROVIDER", raising=False)
    monkeypatch.setattr(settings_module, "_DOTENV_LOADED", False)

    first = settings_module.get_settings()
    dotenv_path.write_text("AGENT_LLM_PROVIDER=minimax\n", encoding="utf-8")
    second = settings_module.get_settings()

    assert first.llm_provider == "fake"
    assert second.llm_provider == "fake"
