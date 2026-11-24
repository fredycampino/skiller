import json
from pathlib import Path

from skiller.domain.agent.llm.provider_catalog import LLMAdapterType, LLMProviderDefinition
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
        *,
        known_provider_names: frozenset[str],
    ) -> tuple[LLMProviderCatalogOverride, ...]:
        raw_config = _load_json_object(path)
        providers = raw_config.get("providers")
        if isinstance(providers, dict):
            supported_adapters = {adapter.value for adapter in LLMAdapterType}
            supported = {}
            for name, entry in providers.items():
                if isinstance(entry, dict):
                    adapter = entry.get("adapter")
                    if isinstance(adapter, str) and adapter not in supported_adapters:
                        continue
                    if "adapter" not in entry and name not in known_provider_names:
                        continue
                supported[name] = entry
            raw_config = {**raw_config, "providers": supported}
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
