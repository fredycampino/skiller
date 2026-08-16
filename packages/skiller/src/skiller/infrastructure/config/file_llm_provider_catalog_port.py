from collections.abc import Mapping
from pathlib import Path

from skiller.domain.agent.llm.provider_catalog import (
    LLMProviderCatalog,
    LLMProviderCatalogSource,
)
from skiller.domain.agent.llm.provider_catalog_port import LLMProviderCatalogPort
from skiller.infrastructure.config.file_llm_provider_catalog_datasource import (
    FileLLMProviderCatalogDatasource,
)
from skiller.infrastructure.config.file_llm_provider_catalog_mapper import (
    FileLLMProviderCatalogMapper,
)
from skiller.infrastructure.config.provider_catalog_schema import (
    LLMProviderConfigModel,
)

_API_KEY_FIELDS = frozenset({"api_key", "api_key_env", "api_key_file"})


class FileLLMProviderCatalogPort(LLMProviderCatalogPort):
    def __init__(
        self,
        *,
        datasource: FileLLMProviderCatalogDatasource,
        mapper: FileLLMProviderCatalogMapper,
        default_path: Path,
        user_path: Path | None,
        env: Mapping[str, str],
    ) -> None:
        self.datasource = datasource
        self.mapper = mapper
        self.default_path = default_path
        self.user_path = user_path
        self.env = env

    def get_catalog(self) -> LLMProviderCatalog:
        providers = self.datasource.get_providers(self.default_path)
        sources = {provider.name: LLMProviderCatalogSource.DEFAULT for provider in providers}
        if self.user_path is not None and self.user_path.exists():
            user_providers = self.datasource.get_providers(self.user_path)
            providers = self._merge_providers(providers, user_providers)
            sources.update(
                {provider.name: LLMProviderCatalogSource.USER for provider in user_providers}
            )
        env_path_value = self.env.get("AGENT_PROVIDERS_FILE", "").strip()
        if env_path_value:
            env_path = Path(env_path_value).expanduser()
            env_providers = self.datasource.get_providers(env_path)
            providers = self._merge_providers(providers, env_providers)
            sources.update(
                {provider.name: LLMProviderCatalogSource.ENV for provider in env_providers}
            )
        catalog = self.mapper.to_catalog(providers)
        return LLMProviderCatalog(providers=catalog.providers, sources=sources)

    def _merge_providers(
        self,
        base: tuple[LLMProviderConfigModel, ...],
        override: tuple[LLMProviderConfigModel, ...],
    ) -> tuple[LLMProviderConfigModel, ...]:
        providers_by_name = {provider.name: provider for provider in base}
        for override_provider in override:
            base_provider = providers_by_name.get(override_provider.name)
            if base_provider is None:
                providers_by_name[override_provider.name] = override_provider
                continue
            providers_by_name[override_provider.name] = self._merge_provider(
                base=base_provider,
                override=override_provider,
            )
        return tuple(providers_by_name.values())

    def _merge_provider(
        self,
        *,
        base: LLMProviderConfigModel,
        override: LLMProviderConfigModel,
    ) -> LLMProviderConfigModel:
        adapter_changed = (
            base.adapter is not None
            and override.adapter is not None
            and base.adapter != override.adapter
        )
        if adapter_changed:
            raise ValueError(f"LLM provider adapter cannot be changed: {base.name}")

        override_fields = override.model_fields_set - {"name"}
        updates = {field_name: getattr(override, field_name) for field_name in override_fields}
        if override_fields & _API_KEY_FIELDS:
            api_key_updates = {
                field_name: getattr(override, field_name) for field_name in _API_KEY_FIELDS
            }
            updates.update(api_key_updates)
        return base.model_copy(update=updates)
