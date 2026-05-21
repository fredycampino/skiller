from __future__ import annotations

import json

import pytest

from skiller.domain.agent.agent_config_model import AgentLLMClientType, AgentLLMProviderType
from skiller.domain.agent.agent_config_validation_model import (
    AgentConfigValidation,
    AgentConfigValidationErrorCode,
)
from skiller.infrastructure.config.json_agent_config_provider import JsonAgentConfigProvider

pytestmark = pytest.mark.unit


def test_json_agent_config_provider_reads_agent_config(tmp_path) -> None:
    secret_path = tmp_path / "minimax-key"
    secret_path.write_text("secret\n", encoding="utf-8")
    config_path = tmp_path / "agent.json"
    config_path.write_text(
        json.dumps(
            {
                "llm": {
                    "default_provider": "minimax-main",
                    "providers": {
                        "minimax-main": {
                            "provider": "minimax",
                            "client_type": "openai_chat_completions",
                            "api_key_file": str(secret_path),
                            "base_url": "https://api.minimax.io/v1",
                            "model": "MiniMax-M2.5",
                            "timeout_seconds": 30,
                            "context_window_tokens": 1_000_000,
                        }
                    },
                },
                "agent": {
                    "loop": {
                        "max_turns": 12,
                        "max_tool_calls": 7,
                    },
                    "context": {
                        "compaction": {
                            "enabled": True,
                            "max_total_tokens_ratio": 0.9,
                        }
                    },
                    "event_output": {
                        "truncate": {
                            "enabled": False,
                            "max_text_chars": 300,
                            "max_json_chars": 2000,
                            "max_array_items": 8,
                        }
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    config = JsonAgentConfigProvider(config_path=config_path, env={}).get_config()
    provider = config.llm.default()

    assert config.llm.default_provider == "minimax-main"
    assert provider.provider == AgentLLMProviderType.MINIMAX
    assert provider.client_type == AgentLLMClientType.OPENAI_CHAT_COMPLETIONS
    assert provider.api_key == "secret"
    assert provider.base_url == "https://api.minimax.io/v1"
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


def test_json_agent_config_provider_applies_supported_env_overrides(tmp_path) -> None:
    config_path = tmp_path / "agent.json"
    config_path.write_text(
        json.dumps(
            {
                "llm": {
                    "default_provider": "minimax-main",
                    "providers": {
                        "minimax-main": {
                            "provider": "minimax",
                            "client_type": "openai_chat_completions",
                            "api_key": "file-key",
                            "base_url": "https://file.minimax.io/v1",
                            "model": "MiniMax-M2.5",
                            "timeout_seconds": 30,
                            "context_window_tokens": 1_000_000,
                        }
                    },
                },
                "agent": {
                    "loop": {
                        "max_turns": 12,
                        "max_tool_calls": 7,
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    env = {
        "AGENT_MINIMAX_API_KEY": "env-key",
        "AGENT_MINIMAX_BASE_URL": "https://env.minimax.io/v1",
        "AGENT_MINIMAX_MODEL": "MiniMax-M2.7",
        "AGENT_MINIMAX_TIMEOUT_SECONDS": "10.5",
        "AGENT_LOOP_MAX_TURNS": "20",
        "AGENT_LOOP_MAX_TOOL_CALLS": "3",
        "AGENT_EVENT_OUTPUT_TRUNCATE_ENABLED": "false",
        "AGENT_EVENT_OUTPUT_MAX_TEXT_CHARS": "100",
    }

    config = JsonAgentConfigProvider(config_path=config_path, env=env).get_config()
    provider = config.llm.default()

    assert provider.api_key == "env-key"
    assert provider.base_url == "https://env.minimax.io/v1"
    assert provider.model == "MiniMax-M2.7"
    assert provider.timeout_seconds == 10.5
    assert config.loop.max_turns == 20
    assert config.loop.max_tool_calls == 3
    assert config.event_output.truncate.enabled is False
    assert config.event_output.truncate.max_text_chars == 100


def test_json_agent_config_provider_resolves_api_key_env(tmp_path) -> None:
    config_path = tmp_path / "agent.json"
    config_path.write_text(
        json.dumps(
            {
                "llm": {
                    "default_provider": "minimax-main",
                    "providers": {
                        "minimax-main": {
                            "provider": "minimax",
                            "client_type": "openai_chat_completions",
                            "api_key_env": "TEST_MINIMAX_KEY",
                            "base_url": "https://api.minimax.io/v1",
                            "model": "MiniMax-M2.5",
                            "timeout_seconds": 30,
                            "context_window_tokens": 1_000_000,
                        }
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    config = JsonAgentConfigProvider(
        config_path=config_path,
        env={"TEST_MINIMAX_KEY": "env-ref-key"},
    ).get_config()

    assert config.llm.default().api_key == "env-ref-key"


def test_json_agent_config_provider_validates_valid_config(tmp_path) -> None:
    config_path = tmp_path / "agent.json"
    config_path.write_text(
        json.dumps(
            {
                "llm": {
                    "default_provider": "minimax-main",
                    "providers": {
                        "minimax-main": {
                            "provider": "minimax",
                            "client_type": "openai_chat_completions",
                            "api_key": "secret",
                            "base_url": "https://api.minimax.io/v1",
                            "model": "MiniMax-M2.5",
                            "timeout_seconds": 30,
                            "context_window_tokens": 1_000_000,
                        }
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    validation = JsonAgentConfigProvider(config_path=config_path, env={}).validate_config()

    assert validation == AgentConfigValidation.valid()


def test_json_agent_config_provider_validates_missing_config_file(tmp_path) -> None:
    config_path = tmp_path / "missing-agent.json"

    validation = JsonAgentConfigProvider(config_path=config_path, env={}).validate_config()

    assert validation == AgentConfigValidation.invalid(
        error=AgentConfigValidationErrorCode.CONFIG_NOT_FOUND,
        message=f"Missing agent config file: {config_path}",
    )


def test_json_agent_config_provider_validates_unsupported_model(tmp_path) -> None:
    config_path = tmp_path / "agent.json"
    config_path.write_text(
        json.dumps(
            {
                "llm": {
                    "default_provider": "minimax-main",
                    "providers": {
                        "minimax-main": {
                            "provider": "minimax",
                            "client_type": "openai_chat_completions",
                            "api_key": "secret",
                            "base_url": "https://api.minimax.io/v1",
                            "model": "not-a-minimax-model",
                            "timeout_seconds": 30,
                            "context_window_tokens": 1_000_000,
                        }
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    validation = JsonAgentConfigProvider(config_path=config_path, env={}).validate_config()

    assert validation.error == AgentConfigValidationErrorCode.PROVIDER_MODEL_UNSUPPORTED
    assert validation.message.startswith(
        "Unsupported model='not-a-minimax-model' for provider='minimax'"
    )


def test_json_agent_config_provider_ignores_config_for_other_ports(tmp_path) -> None:
    config_path = tmp_path / "agent.json"
    config_path.write_text(
        json.dumps(
            {
                "llm": {
                    "default_provider": "minimax-main",
                    "providers": {
                        "minimax-main": {
                            "provider": "minimax",
                            "client_type": "openai_chat_completions",
                            "api_key": "secret",
                            "base_url": "https://api.minimax.io/v1",
                            "model": "MiniMax-M2.5",
                            "timeout_seconds": 30,
                            "context_window_tokens": 1_000_000,
                        }
                    },
                },
                "shell": {
                    "policy": {
                        "allowlist": {
                            "enabled": True,
                        }
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    config = JsonAgentConfigProvider(config_path=config_path, env={}).get_config()

    assert config.llm.default().api_key == "secret"


def test_json_agent_config_provider_rejects_unknown_provider_type(tmp_path) -> None:
    config_path = tmp_path / "agent.json"
    config_path.write_text(
        json.dumps(
            {
                "llm": {
                    "default_provider": "bad",
                    "providers": {
                        "bad": {
                            "provider": "bad",
                            "client_type": "openai_chat_completions",
                            "api_key": "secret",
                            "base_url": "https://api.example.com/v1",
                            "model": "model",
                            "timeout_seconds": 30,
                            "context_window_tokens": 100_000,
                        }
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Invalid agent config"):
        JsonAgentConfigProvider(config_path=config_path, env={}).get_config()


def test_json_agent_config_provider_rejects_legacy_provider_type_field(tmp_path) -> None:
    config_path = tmp_path / "agent.json"
    config_path.write_text(
        json.dumps(
            {
                "llm": {
                    "default_provider": "minimax-main",
                    "providers": {
                        "minimax-main": {
                            "type": "minimax",
                            "client_type": "openai_chat_completions",
                            "api_key": "secret",
                            "base_url": "https://api.example.com/v1",
                            "model": "model",
                            "timeout_seconds": 30,
                            "context_window_tokens": 100_000,
                        }
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Invalid agent config"):
        JsonAgentConfigProvider(config_path=config_path, env={}).get_config()


def test_json_agent_config_provider_rejects_unsupported_provider_model(tmp_path) -> None:
    config_path = tmp_path / "agent.json"
    config_path.write_text(
        json.dumps(
            {
                "llm": {
                    "default_provider": "minimax-main",
                    "providers": {
                        "minimax-main": {
                            "provider": "minimax",
                            "client_type": "openai_chat_completions",
                            "api_key": "secret",
                            "base_url": "https://api.minimax.io/v1",
                            "model": "not-a-minimax-model",
                            "timeout_seconds": 30,
                            "context_window_tokens": 100_000,
                        }
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="Unsupported model='not-a-minimax-model' for provider='minimax'",
    ):
        JsonAgentConfigProvider(config_path=config_path, env={}).get_config()


def test_json_agent_config_provider_rejects_unsupported_env_model_override(
    tmp_path,
) -> None:
    config_path = tmp_path / "agent.json"
    config_path.write_text(
        json.dumps(
            {
                "llm": {
                    "default_provider": "minimax-main",
                    "providers": {
                        "minimax-main": {
                            "provider": "minimax",
                            "client_type": "openai_chat_completions",
                            "api_key": "secret",
                            "base_url": "https://api.minimax.io/v1",
                            "model": "MiniMax-M2.5",
                            "timeout_seconds": 30,
                            "context_window_tokens": 100_000,
                        }
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="Unsupported model='env-model' for provider='minimax'",
    ):
        JsonAgentConfigProvider(
            config_path=config_path,
            env={"AGENT_MINIMAX_MODEL": "env-model"},
        ).get_config()


def test_json_agent_config_provider_rejects_provider_client_type_mismatch(
    tmp_path,
) -> None:
    config_path = tmp_path / "agent.json"
    config_path.write_text(
        json.dumps(
            {
                "llm": {
                    "default_provider": "minimax-main",
                    "providers": {
                        "minimax-main": {
                            "provider": "minimax",
                            "client_type": "fake",
                            "api_key": "secret",
                            "base_url": "https://api.minimax.io/v1",
                            "model": "MiniMax-M2.5",
                            "timeout_seconds": 30,
                            "context_window_tokens": 100_000,
                        }
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="Unsupported client_type='fake' for provider='minimax'",
    ):
        JsonAgentConfigProvider(config_path=config_path, env={}).get_config()
