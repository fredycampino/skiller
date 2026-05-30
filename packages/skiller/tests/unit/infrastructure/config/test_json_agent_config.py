from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

import pytest

from skiller.application.tools.files import FilesTool, FilesToolRuntimeConfig
from skiller.application.tools.notify import NotifyTool
from skiller.application.tools.shell import ShellProcessTool
from skiller.application.tools.shell.config import ShellToolRuntimeConfig
from skiller.domain.agent.agent_config_validation_model import (
    AgentConfigValidation,
    AgentConfigValidationErrorCode,
)
from skiller.domain.agent.agent_llm_provider_model import AgentLLMProviderType
from skiller.infrastructure.config.agent_config_mapper import AgentConfigMapper
from skiller.infrastructure.config.json_agent_config import JsonAgentConfig

pytestmark = pytest.mark.unit


def test_json_agent_config_reads_agent_config(tmp_path) -> None:
    secret_path = tmp_path / "minimax-key"
    secret_path.write_text("secret\n", encoding="utf-8")
    config_path = tmp_path / "agent.json"
    _write_config(
        config_path,
        llm=_minimax_llm(api_key_file=str(secret_path)),
        loop={"max_turns": 12, "max_tool_calls": 7},
        context={"compaction": {"enabled": True, "max_total_tokens_ratio": 0.9}},
        event_output={
            "truncate": {
                "enabled": False,
                "max_text_chars": 300,
                "max_json_chars": 2000,
                "max_array_items": 8,
            }
        },
    )

    config = _provider(config_path=config_path, env={}).get_config()
    provider = config.llm.default()

    assert config.llm.default_provider == AgentLLMProviderType.MINIMAX
    assert provider.type == AgentLLMProviderType.MINIMAX
    assert provider.api_key == "secret"
    assert provider.model == "MiniMax-M2.5"
    assert provider.timeout_seconds == 30.0
    assert provider.context_window_tokens == 1_000_000
    assert config.loop.max_turns == 12
    assert config.loop.max_tool_calls == 7
    assert config.context.compaction.enabled is True
    assert config.context.compaction.max_total_tokens_ratio == 0.9
    assert config.event_output.truncate.enabled is False
    assert config.event_output.truncate.max_text_chars == 300
    assert config.event_output.truncate.max_json_chars == 2000
    assert config.event_output.truncate.max_array_items == 8


def test_json_agent_config_applies_selected_provider_env_overrides(tmp_path) -> None:
    config_path = tmp_path / "agent.json"
    _write_config(config_path, llm=_minimax_llm(api_key="file-key"))
    env = {
        "AGENT_MINIMAX_API_KEY": "env-key",
        "AGENT_MINIMAX_MODEL": "MiniMax-M2.7",
        "AGENT_MINIMAX_TIMEOUT_SECONDS": "10.5",
        "AGENT_LOOP_MAX_TURNS": "20",
        "AGENT_LOOP_MAX_TOOL_CALLS": "3",
        "AGENT_EVENT_OUTPUT_TRUNCATE_ENABLED": "false",
        "AGENT_EVENT_OUTPUT_MAX_TEXT_CHARS": "100",
    }

    config = _provider(config_path=config_path, env=env).get_config()
    provider = config.llm.default()

    assert provider.api_key == "env-key"
    assert provider.model == "MiniMax-M2.7"
    assert provider.timeout_seconds == 10.5
    assert config.loop.max_turns == 20
    assert config.loop.max_tool_calls == 3
    assert config.event_output.truncate.enabled is False
    assert config.event_output.truncate.max_text_chars == 100


def test_json_agent_config_applies_llm_max_context_tokens_to_selected_provider(
    tmp_path,
) -> None:
    config_path = tmp_path / "agent.json"
    payload = _minimax_llm(api_key="secret")
    payload["llm"] = {
        "default_provider": "minimax",
        "max_context_tokens": 80_000,
    }
    config_path.write_text(json.dumps(payload), encoding="utf-8")

    config = _provider(config_path=config_path, env={}).get_config()

    assert config.llm.default().context_window_tokens == 80_000


def test_json_agent_config_resolves_api_key_env(tmp_path) -> None:
    config_path = tmp_path / "agent.json"
    _write_config(config_path, llm=_minimax_llm(api_key_env="TEST_MINIMAX_KEY"))

    config = _provider(
        config_path=config_path,
        env={"TEST_MINIMAX_KEY": "env-ref-key"},
    ).get_config()

    assert config.llm.default().api_key == "env-ref-key"


def test_json_agent_config_reads_codex_provider(tmp_path) -> None:
    credentials_path = tmp_path / "openai-codex.json"
    credentials_path.write_text('{"access_token":"token"}', encoding="utf-8")
    config_path = tmp_path / "agent.json"
    _write_config(config_path, llm=_codex_llm(credentials_file=str(credentials_path)))

    config = _provider(config_path=config_path, env={}).get_config()
    provider = config.llm.default()

    assert config.llm.default_provider == AgentLLMProviderType.CODEX
    assert provider.type == AgentLLMProviderType.CODEX
    assert provider.credentials_file == str(credentials_path)


def test_json_agent_config_rejects_codex_without_credentials_file(tmp_path) -> None:
    config_path = tmp_path / "agent.json"
    _write_config(config_path, llm=_codex_llm(credentials_file=None))

    with pytest.raises(ValueError, match="LLM provider requires credentials_file"):
        _provider(config_path=config_path, env={}).get_config()


def test_json_agent_config_loads_tool_runtime_config(tmp_path) -> None:
    config_path = tmp_path / "agent.json"
    _write_config(
        config_path,
        llm=_minimax_llm(api_key="secret"),
        tools={
            "files": {
                "read": ["."],
                "write": ["src"],
                "all": ["shared"],
            },
            "shell": {
                "allowed_paths": ["tmp/work", "~/agent"],
                "allowlist_enabled": True,
                "allow_env_prefix": False,
                "allowed_commands": ["rg", "cat"],
            },
            "notify": {"ignored": True},
        },
    )

    config = _provider(config_path=config_path, env={}).get_config()

    assert config.tools.get("shell") == ShellToolRuntimeConfig(
        definition=ShellProcessTool,
        allowed_paths=(
            Path("tmp/work").resolve(strict=False),
            Path("~/agent").expanduser().resolve(strict=False),
        ),
        allowlist_enabled=True,
        allow_env_prefix=False,
        allowed_commands=("rg", "cat"),
    )
    assert config.tools.get("files") == FilesToolRuntimeConfig(
        definition=FilesTool,
        read=(Path("."),),
        write=(Path("src"),),
        all=(Path("shared"),),
    )
    assert config.tools.get("notify") is None


def test_json_agent_config_validates_valid_config(tmp_path) -> None:
    config_path = tmp_path / "agent.json"
    _write_config(config_path, llm=_minimax_llm(api_key="secret"))

    validation = _provider(config_path=config_path, env={}).validate_config()

    assert validation == AgentConfigValidation.valid()


def test_json_agent_config_rejects_agent_wrapper(tmp_path) -> None:
    config_path = tmp_path / "agent.json"
    _write_config(config_path, llm=_minimax_llm(api_key="secret"), agent={})

    validation = _provider(config_path=config_path, env={}).validate_config()

    assert validation == AgentConfigValidation.invalid(
        error=AgentConfigValidationErrorCode.INVALID_SCHEMA,
        message="agent.json field 'agent' is not supported",
    )


def test_json_agent_config_validates_missing_config_file(tmp_path) -> None:
    config_path = tmp_path / "missing-agent.json"

    validation = _provider(config_path=config_path, env={}).validate_config()

    assert validation == AgentConfigValidation.invalid(
        error=AgentConfigValidationErrorCode.CONFIG_NOT_FOUND,
        message=f"Missing agent config file: {config_path}",
    )


def test_json_agent_config_validates_unsupported_model(tmp_path) -> None:
    config_path = tmp_path / "agent.json"
    _write_config(
        config_path,
        llm=_minimax_llm(api_key="secret", model="not-a-minimax-model"),
    )

    validation = _provider(config_path=config_path, env={}).validate_config()

    assert validation.error == AgentConfigValidationErrorCode.PROVIDER_MODEL_UNSUPPORTED
    assert validation.message.startswith(
        "Unsupported model='not-a-minimax-model' for provider='minimax'"
    )


def test_json_agent_config_resolves_config_file_precedence(tmp_path) -> None:
    global_config_path = tmp_path / "global-agent.json"
    context_config_path = tmp_path / "context-agent.json"
    env_config_path = tmp_path / "env-agent.json"
    _write_config(global_config_path, llm=_fake_llm())
    _write_config(context_config_path, llm=_null_llm())
    _write_config(env_config_path, llm=_minimax_llm(api_key="secret"))

    context_config = _provider(config_path=global_config_path, env={}).get_config(
        config_path=context_config_path
    )
    env_config = _provider(
        config_path=global_config_path,
        env={"AGENT_AGENT_CONFIG_FILE": str(env_config_path)},
    ).get_config(config_path=context_config_path)
    fallback_config = _provider(config_path=global_config_path, env={}).get_config(
        config_path=tmp_path / "missing-agent.json"
    )

    assert context_config.llm.default_provider == AgentLLMProviderType.NULL
    assert env_config.llm.default_provider == AgentLLMProviderType.MINIMAX
    assert fallback_config.llm.default_provider == AgentLLMProviderType.FAKE


def test_json_agent_config_overrides_root_sections_without_deep_merge(tmp_path) -> None:
    global_config_path = tmp_path / "global-agent.json"
    context_config_path = tmp_path / "context-agent.json"
    _write_config(
        global_config_path,
        llm=_minimax_llm(api_key="secret"),
        loop={"max_turns": 12, "max_tool_calls": 7},
        tools={
            "shell": {
                "allowed_paths": ["."],
                "allowlist_enabled": True,
                "allow_env_prefix": True,
                "allowed_commands": ["pwd"],
            },
        },
    )
    _write_config(
        context_config_path,
        llm=_fake_llm(),
        loop={"max_turns": 3},
        tools={
            "files": {
                "read": ["."],
                "write": [],
                "all": [],
            },
        },
    )

    config = _provider(config_path=global_config_path, env={}).get_config(
        config_path=context_config_path
    )

    assert config.llm.default_provider == AgentLLMProviderType.FAKE
    assert config.loop.max_turns == 3
    assert config.loop.max_tool_calls == 5
    assert config.tools.get("shell") == ShellToolRuntimeConfig(
        definition=ShellProcessTool,
        allowed_paths=(),
        allowlist_enabled=False,
        allow_env_prefix=True,
        allowed_commands=(),
    )
    assert config.tools.get("files") == FilesToolRuntimeConfig(
        definition=FilesTool,
        read=(Path("."),),
        write=(),
        all=(),
    )


def test_json_agent_config_agent_can_override_default_provider_only(tmp_path) -> None:
    global_config_path = tmp_path / "global-agent.json"
    context_config_path = tmp_path / "context-agent.json"
    _write_config(
        global_config_path,
        llm={
            "llm": {"default_provider": "minimax"},
            "providers": {
                "minimax": {
                    "api_key": "secret",
                    "model": "MiniMax-M2.5",
                    "timeout_seconds": 30,
                    "context_window_tokens": 1_000_000,
                },
                "fake": {
                    "model": "model1",
                    "timeout_seconds": 30,
                    "context_window_tokens": 100_000,
                },
            },
        },
    )
    _write_config(
        context_config_path,
        llm={
            "llm": {"default_provider": "fake"},
        },
    )

    config = _provider(config_path=global_config_path, env={}).get_config(
        config_path=context_config_path
    )

    provider = config.llm.default()

    assert provider.type == AgentLLMProviderType.FAKE
    assert provider.model == "model1"


def test_json_agent_config_does_not_use_cwd_agent_json(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_config(tmp_path / "agent.json", llm=_null_llm())
    global_config_path = tmp_path / "global-agent.json"
    _write_config(global_config_path, llm=_fake_llm())
    monkeypatch.chdir(tmp_path)

    config = _provider(config_path=global_config_path, env={}).get_config()

    assert config.llm.default_provider == AgentLLMProviderType.FAKE


def test_json_agent_config_rejects_unknown_provider(tmp_path) -> None:
    config_path = tmp_path / "agent.json"
    _write_config(
        config_path,
        llm={
            "llm": {"default_provider": "bad"},
            "providers": {
                "bad": {
                    "api_key": "secret",
                    "model": "model",
                    "timeout_seconds": 30,
                    "context_window_tokens": 100_000,
                }
            },
        },
    )

    with pytest.raises(ValueError, match="Unsupported LLM provider: bad"):
        _provider(config_path=config_path, env={}).get_config()


def test_json_agent_config_rejects_unsupported_env_model_override(tmp_path) -> None:
    config_path = tmp_path / "agent.json"
    _write_config(config_path, llm=_minimax_llm(api_key="secret"))

    with pytest.raises(
        ValueError,
        match="Unsupported model='env-model' for provider='minimax'",
    ):
        _provider(
            config_path=config_path,
            env={"AGENT_MINIMAX_MODEL": "env-model"},
        ).get_config()


def _write_config(
    path: Path,
    *,
    llm: dict[str, object],
    **sections: object,
) -> None:
    payload: dict[str, object] = dict(llm)
    payload.update(sections)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _minimax_llm(
    *,
    api_key: str | None = None,
    api_key_env: str | None = None,
    api_key_file: str | None = None,
    model: str = "MiniMax-M2.5",
    extra: dict[str, object] | None = None,
) -> dict[str, object]:
    provider: dict[str, object] = {
        "model": model,
        "timeout_seconds": 30,
        "context_window_tokens": 1_000_000,
    }
    if api_key is not None:
        provider["api_key"] = api_key
    if api_key_env is not None:
        provider["api_key_env"] = api_key_env
    if api_key_file is not None:
        provider["api_key_file"] = api_key_file
    if extra is not None:
        provider.update(extra)

    return {
        "llm": {"default_provider": "minimax"},
        "providers": {
            "minimax": provider,
        },
    }


def _codex_llm(*, credentials_file: str | None) -> dict[str, object]:
    provider: dict[str, object] = {
        "model": "gpt-5.5",
        "timeout_seconds": 120,
        "context_window_tokens": 100_000,
    }
    if credentials_file is not None:
        provider["credentials_file"] = credentials_file

    return {
        "llm": {"default_provider": "codex"},
        "providers": {
            "codex": provider,
        },
    }


def _fake_llm() -> dict[str, object]:
    return {
        "llm": {"default_provider": "fake"},
        "providers": {
            "fake": {
                "model": "model1",
                "timeout_seconds": 30,
                "context_window_tokens": 100_000,
            }
        },
    }


def _null_llm() -> dict[str, object]:
    return {
        "llm": {"default_provider": "null"},
        "providers": {
            "null": {
                "model": "null1",
                "timeout_seconds": 30,
                "context_window_tokens": 100_000,
            }
        },
    }


def _provider(
    *,
    config_path: Path,
    env: Mapping[str, str],
) -> JsonAgentConfig:
    return JsonAgentConfig(
        config_path_global=config_path,
        config_mapper=AgentConfigMapper(
            env=env,
            tools=(
                FilesTool(),
                ShellProcessTool(),
                NotifyTool(),
            ),
        ),
        env=env,
    )
