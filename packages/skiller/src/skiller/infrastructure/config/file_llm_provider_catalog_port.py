"""File-backed LLM provider catalog port.

Merges the default catalog, the optional user catalog, and the optional
env-file catalog into a single LLMProviderCatalog. The merge is by
provider name: an override entry replaces the base entry with the same
name. Since provider definitions are frozen dataclasses, merging two
instances of the same adapter is done via `dataclasses.replace`.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from skiller.domain.agent.llm.provider_catalog import (
    LLMProviderCatalog,
    LLMProviderCatalogSource,
    LLMProviderDefinition,
)
from skiller.domain.agent.llm.provider_catalog_port import LLMProviderCatalogPort
from skiller.infrastructure.config.adapter_config import LLMProviderCatalogOverride
from skiller.infrastructure.config.file_llm_provider_catalog_datasource import (
    FileLLMProviderCatalogDatasource,
)
from skiller.infrastructure.config.file_llm_provider_catalog_mapper import (
    FileLLMProviderCatalogMapper,
)


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
            user_overrides = self.datasource.get_override_providers(self.user_path)
            providers = self._merge_overrides(providers, user_overrides)
            sources.update(
                {override.name: LLMProviderCatalogSource.USER for override in user_overrides}
            )
        env_path_value = self.env.get("AGENT_PROVIDERS_FILE", "").strip()
        if env_path_value:
            env_path = Path(env_path_value).expanduser()
            env_overrides = self.datasource.get_override_providers(env_path)
            providers = self._merge_overrides(providers, env_overrides)
            sources.update(
                {override.name: LLMProviderCatalogSource.ENV for override in env_overrides}
            )
        catalog = self.mapper.to_catalog(providers)
        return LLMProviderCatalog(providers=catalog.providers, sources=sources)

    def _merge_overrides(
        self,
        base: tuple[LLMProviderDefinition, ...],
        overrides: tuple[LLMProviderCatalogOverride, ...],
    ) -> tuple[LLMProviderDefinition, ...]:
        providers_by_name = {provider.name: provider for provider in base}
        for override in overrides:
            name = override.name
            base_provider = providers_by_name.get(name)
            if base_provider is None:
                providers_by_name[name] = self.mapper.to_new_provider(override)
                continue
            providers_by_name[name] = self._merge_provider(
                base=base_provider,
                override=override,
            )
        return tuple(providers_by_name.values())

    def _merge_provider(
        self,
        *,
        base: LLMProviderDefinition,
        override: LLMProviderCatalogOverride,
    ) -> LLMProviderDefinition:
        return self.mapper.apply_override(base=base, override=override)
