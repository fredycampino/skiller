from pathlib import Path

import pytest

from skiller.domain.agent.llm.model import LLMToolChoiceMode
from skiller.domain.agent.llm.provider_catalog import (
    BedrockLLMProviderDefinition,
    CodexLLMProviderDefinition,
    LLMAdapterType,
    LLMApiKeySourceType,
    OpenAILLMProviderDefinition,
)
from skiller.infrastructure.config import file_llm_provider_catalog_mapper
from skiller.infrastructure.config.file_llm_provider_catalog_mapper import (
    FileLLMProviderCatalogMapper,
)

pytestmark = pytest.mark.unit


def test_mapper_builds_openai_domain_provider() -> None:
    mapper = FileLLMProviderCatalogMapper()
    configs = mapper.to_provider_configs(
        {
            "providers": {
                "minimax": _openai_entry(),
            }
        }
    )

    provider = mapper.to_catalog(configs).get("minimax")

    assert isinstance(provider, OpenAILLMProviderDefinition)
    assert provider.enabled is True
    assert provider.temperature == 1
    assert provider.top_p == 1
    assert provider.max_output_tokens == 4096
    assert provider.parallel_tool_calls is True
    assert provider.tool_choice == LLMToolChoiceMode.AUTO
    assert provider.api_key_source is not None
    assert provider.api_key_source.type == LLMApiKeySourceType.ENV
    assert provider.api_key_source.value == "PROVIDER_API_KEY"


def test_default_catalog_declares_openrouter_as_openai_compatible() -> None:
    mapper = FileLLMProviderCatalogMapper()
    configs = mapper.to_provider_configs(
        Path("packages/skiller/src/skiller/application/config/providers.json")
    )

    provider = mapper.to_catalog(configs).get("openrouter")

    assert isinstance(provider, OpenAILLMProviderDefinition)
    assert provider.base_url == "https://openrouter.ai/api/v1"
    assert provider.api_key_source is not None
    assert provider.api_key_source.type == LLMApiKeySourceType.ENV
    assert provider.api_key_source.value == "OPENROUTER_API_KEY"
    assert [model.model for model in provider.models] == [
        "openrouter/free",
        "openai/gpt-4o",
        "anthropic/claude-opus-5",
        "deepseek/deepseek-v4-pro",
        "z-ai/glm-5.3",
        "google/gemini-3.7-flash",
        "xiaomi/mimo-v2.5-pro",
        "anthropic/claude-opus-4.8",
    ]


def test_mapper_builds_bedrock_domain_provider() -> None:
    mapper = FileLLMProviderCatalogMapper()
    configs = mapper.to_provider_configs(
        {
            "providers": {
                "bedrock": {
                    "adapter": "bedrock",
                    "enabled": True,
                    "profile": " default ",
                    "timeout_seconds": 45,
                    "max_output_tokens": 4096,
                    "models": [_model("bedrock-model", 200_000)],
                }
            }
        }
    )

    provider = mapper.to_catalog(configs).get("bedrock")

    assert isinstance(provider, BedrockLLMProviderDefinition)
    assert provider.adapter == LLMAdapterType.BEDROCK
    assert provider.profile == "default"
    assert provider.max_output_tokens == 4096


def test_mapper_builds_codex_domain_provider() -> None:
    mapper = FileLLMProviderCatalogMapper()
    configs = mapper.to_provider_configs(
        {
            "providers": {
                "codex": {
                    "adapter": "codex",
                    "enabled": True,
                    "credentials_file": " ~/.skiller/secrets/openai-codex.json ",
                    "timeout_seconds": 120,
                    "max_output_tokens": 4096,
                    "parallel_tool_calls": True,
                    "models": [_model("gpt-5.6-sol", 1_050_000)],
                }
            }
        }
    )

    provider = mapper.to_catalog(configs).get("codex")

    assert isinstance(provider, CodexLLMProviderDefinition)
    assert provider.adapter == LLMAdapterType.CODEX
    assert provider.credentials_file == "~/.skiller/secrets/openai-codex.json"
    assert provider.parallel_tool_calls is True
    assert provider.max_output_tokens == 4096


def test_mapper_rejects_openai_fields_for_codex_provider() -> None:
    mapper = FileLLMProviderCatalogMapper()

    with pytest.raises(ValueError, match="Invalid LLM provider catalog"):
        mapper.to_provider_configs(
            {
                "providers": {
                    "codex": {
                        "adapter": "codex",
                        "enabled": True,
                        "credentials_file": "~/.skiller/secrets/openai-codex.json",
                        "timeout_seconds": 120,
                        "max_output_tokens": 4096,
                        "parallel_tool_calls": True,
                        "temperature": 1,
                        "models": [_model("gpt-5.6-sol", 1_050_000)],
                    }
                }
            }
        )


def test_mapper_rejects_bedrock_fields_for_openai_provider() -> None:
    mapper = FileLLMProviderCatalogMapper()

    with pytest.raises(ValueError, match="Invalid LLM provider catalog"):
        mapper.to_provider_configs(
            {
                "providers": {
                    "minimax": {
                        "adapter": "openai",
                        "enabled": True,
                        "base_url": "https://provider.example/v1",
                        "api_key_env": "PROVIDER_API_KEY",
                        "timeout_seconds": 30,
                        "temperature": 1,
                        "top_p": 1,
                        "max_output_tokens": 4096,
                        "parallel_tool_calls": True,
                        "tool_choice": "auto",
                        "profile": "default",
                        "models": [_model("m", 1)],
                    }
                }
            }
        )


def test_mapper_rejects_multiple_api_key_sources() -> None:
    mapper = FileLLMProviderCatalogMapper()

    with pytest.raises(
        ValueError,
        match="only one api_key source",
    ):
        mapper.to_provider_configs(
            {
                "providers": {
                    "minimax": {
                        "adapter": "openai",
                        "enabled": True,
                        "base_url": "https://provider.example/v1",
                        "api_key": "secret",
                        "api_key_env": "MINIMAX_API_KEY",
                        "timeout_seconds": 30,
                        "temperature": 1,
                        "top_p": 1,
                        "max_output_tokens": 4096,
                        "parallel_tool_calls": True,
                        "tool_choice": "auto",
                        "models": [_model("m", 1)],
                    }
                }
            }
        )


def test_mapper_rejects_missing_required_field() -> None:
    mapper = FileLLMProviderCatalogMapper()

    with pytest.raises(ValueError, match="Invalid LLM provider catalog"):
        mapper.to_provider_configs(
            {
                "providers": {
                    "lmstudio": {
                        "adapter": "openai",
                        "enabled": True,
                        "api_key_env": "KEY",
                        "timeout_seconds": 30,
                        "temperature": 1,
                        "top_p": 1,
                        "max_output_tokens": 4096,
                        "parallel_tool_calls": True,
                        "tool_choice": "auto",
                        "models": [_model("local-model", 128_000)],
                    }
                }
            }
        )


def test_mapper_rejects_unknown_field() -> None:
    mapper = FileLLMProviderCatalogMapper()

    with pytest.raises(ValueError, match="Invalid LLM provider catalog"):
        mapper.to_provider_configs(
            {
                "providers": {
                    "minimax": {
                        "adapter": "openai",
                        "enabled": True,
                        "base_url": "https://provider.example/v1",
                        "api_key_env": "KEY",
                        "timeout_seconds": 30,
                        "temperature": 1,
                        "top_p": 1,
                        "max_output_tokens": 4096,
                        "parallel_tool_calls": True,
                        "tool_choice": "auto",
                        "unknown_field": 1,
                        "models": [_model("m", 1)],
                    }
                }
            }
        )


def test_mapper_rejects_explicit_null_field() -> None:
    mapper = FileLLMProviderCatalogMapper()

    with pytest.raises(ValueError, match="Invalid LLM provider catalog"):
        mapper.to_provider_configs(
            {
                "providers": {
                    "minimax": {
                        "adapter": "openai",
                        "enabled": True,
                        "base_url": "https://provider.example/v1",
                        "api_key_env": "KEY",
                        "timeout_seconds": None,
                        "temperature": 1,
                        "top_p": 1,
                        "max_output_tokens": 4096,
                        "parallel_tool_calls": True,
                        "tool_choice": "auto",
                        "models": [_model("m", 1)],
                    }
                }
            }
        )


def test_mapper_rejects_zero_max_output_tokens() -> None:
    mapper = FileLLMProviderCatalogMapper()
    entry = _openai_entry()
    entry["max_output_tokens"] = 0

    with pytest.raises(ValueError, match="Invalid LLM provider catalog"):
        mapper.to_provider_configs({"providers": {"minimax": entry}})


def test_mapper_injects_provider_name_from_map_key() -> None:
    mapper = FileLLMProviderCatalogMapper()
    configs = mapper.to_provider_configs(
        {
            "providers": {
                "minimax": _openai_entry(),
            }
        }
    )

    assert configs[0].name == "minimax"


def test_mapper_returns_named_partial_override() -> None:
    mapper = FileLLMProviderCatalogMapper()

    overrides = mapper.to_override_configs(
        {"providers": {" minimax ": {"timeout_seconds": 60}}},
    )

    assert overrides[0].name == "minimax"
    assert dict(overrides[0].fields) == {"timeout_seconds": 60}


def test_mapper_rejects_explicit_null_override_field() -> None:
    mapper = FileLLMProviderCatalogMapper()

    with pytest.raises(ValueError, match="override fields must not be null: timeout_seconds"):
        mapper.to_override_configs(
            {"providers": {"minimax": {"timeout_seconds": None}}},
        )


def test_mapper_does_not_wrap_non_validation_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_programming_error(_: object) -> object:
        raise RuntimeError("unexpected mapper failure")

    monkeypatch.setattr(
        file_llm_provider_catalog_mapper.LLMProviderCatalogSourceModel,
        "model_validate",
        raise_programming_error,
    )

    with pytest.raises(RuntimeError, match="unexpected mapper failure"):
        FileLLMProviderCatalogMapper().to_provider_configs({"providers": {}})


def test_mapper_rejects_cross_adapter_override_field() -> None:
    mapper = FileLLMProviderCatalogMapper()
    base = mapper.to_catalog(
        mapper.to_provider_configs({"providers": {"minimax": _openai_entry()}}),
    ).get("minimax")
    override = mapper.to_override_configs(
        {"providers": {"minimax": {"profile": "default"}}},
    )[0]

    with pytest.raises(ValueError, match="Invalid LLM provider catalog override"):
        mapper.apply_override(base=base, override=override)


def test_mapper_builds_new_provider_from_complete_override() -> None:
    mapper = FileLLMProviderCatalogMapper()
    entry = _openai_entry()
    entry["api_key_env"] = "CUSTOM_PROVIDER_API_KEY"
    override = mapper.to_override_configs({"providers": {"custom": entry}})[0]

    provider = mapper.to_new_provider(override)

    assert isinstance(provider, OpenAILLMProviderDefinition)
    assert provider.name == "custom"
    assert provider.api_key_source is not None
    assert provider.api_key_source.value == "CUSTOM_PROVIDER_API_KEY"


def _openai_entry() -> dict[str, object]:
    return {
        "adapter": "openai",
        "enabled": True,
        "base_url": "https://provider.example/v1",
        "api_key_env": "PROVIDER_API_KEY",
        "timeout_seconds": 30,
        "temperature": 1,
        "top_p": 1,
        "max_output_tokens": 4096,
        "parallel_tool_calls": True,
        "tool_choice": "auto",
        "models": [_model("MiniMax-M2.7", 204_800)],
    }


def _model(model: str, context_window_tokens: int) -> dict[str, object]:
    return {
        "model": model,
        "context_window_tokens": context_window_tokens,
    }
