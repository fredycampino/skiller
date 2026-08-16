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
                    "timeout_seconds": 60,
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


def _write_catalog(path: Path, catalog: dict[str, object]) -> None:
    path.write_text(json.dumps(catalog), encoding="utf-8")
