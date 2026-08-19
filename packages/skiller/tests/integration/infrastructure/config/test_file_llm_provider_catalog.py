import json
from pathlib import Path

import pytest

from skiller.domain.agent.llm.provider_catalog import LLMAdapterType
from skiller.infrastructure.config.file_llm_provider_catalog_datasource import (
    FileLLMProviderCatalogDatasource,
)
from skiller.infrastructure.config.file_llm_provider_catalog_mapper import (
    FileLLMProviderCatalogMapper,
)
from skiller.infrastructure.config.file_llm_provider_catalog_port import (
    FileLLMProviderCatalogPort,
)

pytestmark = pytest.mark.integration


def test_file_datasource_reads_provider_catalog(tmp_path: Path) -> None:
    path = tmp_path / "providers.json"
    _write_catalog(
        path,
        {
            "providers": {
                "minimax": {
                    "adapter": "openai",
                    "enabled": True,
                    "base_url": "https://provider.example/v1",
                    "api_key_env": "PROVIDER_API_KEY",
                    "timeout_seconds": 60,
                    "temperature": 1,
                    "top_p": 1,
                    "max_output_tokens": 4096,
                    "parallel_tool_calls": True,
                    "tool_choice": "auto",
                    "models": [{"model": "MiniMax-M2.5", "context_window_tokens": 204_800}],
                }
            }
        },
    )
    mapper = FileLLMProviderCatalogMapper()
    datasource = FileLLMProviderCatalogDatasource(mapper=mapper)

    providers = datasource.get_providers(path)

    assert len(providers) == 1
    assert providers[0].name == "minimax"
    assert providers[0].timeout_seconds == 60


def test_file_datasource_rejects_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "providers.json"
    path.write_text("{", encoding="utf-8")
    datasource = FileLLMProviderCatalogDatasource(
        mapper=FileLLMProviderCatalogMapper(),
    )

    with pytest.raises(ValueError, match="Invalid LLM provider catalog JSON"):
        datasource.get_providers(path)


def test_builtin_application_catalog_is_valid() -> None:
    package_path = Path(__file__).parents[4]
    default_path = package_path / "src/skiller/application/config/providers.json"
    mapper = FileLLMProviderCatalogMapper()
    datasource = FileLLMProviderCatalogDatasource(mapper=mapper)
    port = FileLLMProviderCatalogPort(
        datasource=datasource,
        mapper=mapper,
        default_path=default_path,
        user_path=None,
        env={},
    )

    catalog = port.get_catalog()

    assert catalog.get("minimax").adapter == LLMAdapterType.OPENAI
    assert catalog.get("moonshot").adapter == LLMAdapterType.OPENAI
    deepseek = catalog.get("deepseek")
    assert deepseek.adapter == LLMAdapterType.OPENAI
    assert deepseek.base_url == "https://api.deepseek.com"
    assert deepseek.api_key_source is not None
    assert deepseek.api_key_source.type.value == "env"
    assert deepseek.api_key_source.value == "AGENT_DEEPSEEK_API_KEY"
    assert [model.model for model in deepseek.models] == [
        "deepseek-v4-flash",
        "deepseek-v4-pro",
    ]
    assert all(model.context_window_tokens == 128000 for model in deepseek.models)
    lmstudio = catalog.get("lmstudio")
    assert lmstudio.adapter == LLMAdapterType.OPENAI
    assert [model.model for model in lmstudio.models] == [
        "ornith-1.0-9b",
        "google/gemma-4-12b-qat",
    ]
    codex = catalog.get("codex")
    assert codex.adapter == LLMAdapterType.CODEX
    assert [model.model for model in codex.models] == [
        "gpt-5.4",
        "gpt-5.5",
        "gpt-5.6-sol",
        "gpt-5.6-terra",
        "gpt-5.6-luna",
    ]
    assert catalog.get("bedrock").adapter == LLMAdapterType.BEDROCK


def test_file_port_applies_partial_user_override(tmp_path: Path) -> None:
    package_path = Path(__file__).parents[4]
    default_path = package_path / "src/skiller/application/config/providers.json"
    user_path = tmp_path / "providers.json"
    _write_catalog(
        user_path,
        {"providers": {"minimax": {"timeout_seconds": 60}}},
    )
    mapper = FileLLMProviderCatalogMapper()
    port = FileLLMProviderCatalogPort(
        datasource=FileLLMProviderCatalogDatasource(mapper=mapper),
        mapper=mapper,
        default_path=default_path,
        user_path=user_path,
        env={},
    )

    catalog = port.get_catalog()

    assert catalog.get("minimax").timeout_seconds == 60
    assert catalog.source_for("minimax").value == "user"


def test_file_port_adds_complete_custom_provider(tmp_path: Path) -> None:
    package_path = Path(__file__).parents[4]
    default_path = package_path / "src/skiller/application/config/providers.json"
    user_path = tmp_path / "providers.json"
    _write_catalog(
        user_path,
        {
            "providers": {
                "custom": {
                    "adapter": "openai",
                    "enabled": True,
                    "base_url": "https://provider.example/v1",
                    "api_key_env": "CUSTOM_PROVIDER_API_KEY",
                    "timeout_seconds": 30,
                    "temperature": 1,
                    "top_p": 1,
                    "max_output_tokens": 4096,
                    "parallel_tool_calls": True,
                    "tool_choice": "auto",
                    "models": [{"model": "custom-model", "context_window_tokens": 128_000}],
                }
            }
        },
    )
    mapper = FileLLMProviderCatalogMapper()
    port = FileLLMProviderCatalogPort(
        datasource=FileLLMProviderCatalogDatasource(mapper=mapper),
        mapper=mapper,
        default_path=default_path,
        user_path=user_path,
        env={},
    )

    catalog = port.get_catalog()

    assert catalog.get("custom").adapter == LLMAdapterType.OPENAI
    assert catalog.source_for("custom").value == "user"


def _write_catalog(path: Path, catalog: dict[str, object]) -> None:
    path.write_text(json.dumps(catalog), encoding="utf-8")
