import json
from pathlib import Path

from skiller.domain.agent.llm.provider_catalog import LLMProviderDefinition
from skiller.infrastructure.config.adapter_config import LLMProviderCatalogOverride
from skiller.infrastructure.config.file_llm_provider_catalog_mapper import (
    FileLLMProviderCatalogMapper,
)


class FileLLMProviderCatalogDatasource:
    def __init__(
        self,
        *,
        mapper: FileLLMProviderCatalogMapper,
    ) -> None:
        self.mapper = mapper

    def get_providers(
        self,
        path: Path,
    ) -> tuple[LLMProviderDefinition, ...]:
        raw_config = _load_json_object(path)
        return self.mapper.to_provider_configs(raw_config)

    def get_override_providers(
        self,
        path: Path,
    ) -> tuple[LLMProviderCatalogOverride, ...]:
        raw_config = _load_json_object(path)
        return self.mapper.to_override_configs(raw_config)


def _load_json_object(path: Path) -> dict[str, object]:
    if not path.exists():
        raise FileNotFoundError(f"Missing LLM provider catalog: {path}")

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid LLM provider catalog JSON: {path} (line {exc.lineno}, column {exc.colno})"
        ) from exc
    if not isinstance(payload, dict):
        raise ValueError(f"LLM provider catalog must contain a JSON object: {path}")
    return payload
