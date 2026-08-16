import pytest

from skiller.domain.agent.llm.model import LLMToolChoiceMode
from skiller.domain.agent.llm.provider_catalog import (
    BedrockLLMProviderDefinition,
    CodexLLMProviderDefinition,
    LLMAdapterType,
    LLMApiKeySourceType,
    OpenAILLMProviderDefinition,
)
from skiller.infrastructure.config.file_llm_provider_catalog_mapper import (
    FileLLMProviderCatalogMapper,
)

pytestmark = pytest.mark.unit


def test_mapper_returns_normalized_partial_provider_configs() -> None:
    mapper = FileLLMProviderCatalogMapper()

    providers = mapper.to_provider_configs(
        {
            "providers": {
                " minimax ": {
                    "base_url": " https://provider.example/v1 ",
                    "models": [_model(" MiniMax-M2.7 ", 204_800)],
                }
            }
        }
    )

    assert len(providers) == 1
    assert providers[0].name == "minimax"
    assert providers[0].adapter is None
    assert providers[0].base_url == "https://provider.example/v1"
    assert providers[0].models is not None
    assert providers[0].models[0].model == "MiniMax-M2.7"


def test_mapper_builds_openai_domain_provider_with_defaults() -> None:
    mapper = FileLLMProviderCatalogMapper()
    configs = mapper.to_provider_configs(
        {
            "providers": {
                "minimax": _openai_provider(
                    models=[_model("MiniMax-M2.7", 204_800)],
                )
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


def test_mapper_builds_bedrock_domain_provider() -> None:
    mapper = FileLLMProviderCatalogMapper()
    configs = mapper.to_provider_configs(
        {
            "providers": {
                "bedrock": {
                    "adapter": "bedrock",
                    "profile": " default ",
                    "timeout_seconds": 45,
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
                    "credentials_file": " ~/.skiller/secrets/openai-codex.json ",
                    "timeout_seconds": 120,
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


def test_mapper_rejects_openai_fields_for_codex_provider() -> None:
    mapper = FileLLMProviderCatalogMapper()
    configs = mapper.to_provider_configs(
        {
            "providers": {
                "codex": {
                    "adapter": "codex",
                    "credentials_file": "~/.skiller/secrets/openai-codex.json",
                    "timeout_seconds": 120,
                    "temperature": 1,
                    "models": [_model("gpt-5.6-sol", 1_050_000)],
                }
            }
        }
    )

    with pytest.raises(ValueError, match="Codex LLM provider does not accept fields"):
        mapper.to_catalog(configs)


def test_mapper_rejects_multiple_api_key_sources() -> None:
    mapper = FileLLMProviderCatalogMapper()

    with pytest.raises(
        ValueError,
        match="OpenAI LLM provider accepts only one api_key source",
    ):
        mapper.to_provider_configs(
            {
                "providers": {
                    "minimax": {
                        "api_key": "secret",
                        "api_key_env": "MINIMAX_API_KEY",
                    }
                }
            }
        )


def test_mapper_rejects_explicit_null_provider_fields() -> None:
    mapper = FileLLMProviderCatalogMapper()

    with pytest.raises(ValueError, match="fields must not be null"):
        mapper.to_provider_configs(
            {
                "providers": {
                    "minimax": {
                        "timeout_seconds": None,
                    }
                }
            }
        )


def test_mapper_rejects_incomplete_provider() -> None:
    mapper = FileLLMProviderCatalogMapper()
    configs = mapper.to_provider_configs(
        {
            "providers": {
                "lmstudio": {
                    "adapter": "openai",
                    "timeout_seconds": 30,
                    "models": [_model("local-model", 128_000)],
                }
            }
        }
    )

    with pytest.raises(ValueError, match="requires base_url: lmstudio"):
        mapper.to_catalog(configs)


def _openai_provider(
    *,
    models: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "adapter": "openai",
        "base_url": "https://provider.example/v1",
        "api_key_env": "PROVIDER_API_KEY",
        "timeout_seconds": 30,
        "models": models,
    }


def _model(model: str, context_window_tokens: int) -> dict[str, object]:
    return {
        "model": model,
        "context_window_tokens": context_window_tokens,
    }
