import json
from pathlib import Path

from skiller.infrastructure.config.file_llm_provider_catalog_mapper import (
    FileLLMProviderCatalogMapper,
)
from skiller.infrastructure.config.provider_catalog_schema import (
    LLMProviderConfigModel,
)


class FileLLMProviderCatalogDatasource:
    def __init__(
        self,
        *,
        mapper: FileLLMProviderCatalogMapper,
    ) -> None:
        self.mapper = mapper

    def get_providers(self, path: Path) -> tuple[LLMProviderConfigModel, ...]:
        raw_config = _load_json_object(path)
        return self.mapper.to_provider_configs(raw_config)


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
