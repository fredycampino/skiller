from dataclasses import dataclass
from enum import Enum

from skiller.domain.agent.llm.provider_catalog import (
    LLMAdapterType,
    LLMApiKeySourceType,
    LLMProviderCatalogSource,
)
from skiller.domain.agent.llm.provider_catalog_port import LLMProviderCatalogPort


class ListLLMProvidersStatus(str, Enum):
    OK = "OK"
    ERROR = "ERROR"


@dataclass(frozen=True)
class LLMProviderModelItem:
    name: str
    context_window_tokens: int


@dataclass(frozen=True)
class LLMProviderItem:
    name: str
    source: LLMProviderCatalogSource
    adapter: LLMAdapterType
    enabled: bool
    base_url: str | None
    timeout_seconds: float
    credentials_file: str | None
    profile: str | None
    api_key_file: str | None
    models: tuple[LLMProviderModelItem, ...]


@dataclass(frozen=True)
class ListLLMProvidersResult:
    status: ListLLMProvidersStatus
    providers: tuple[LLMProviderItem, ...] = ()
    error: str | None = None


class ListLLMProvidersUseCase:
    def __init__(self, *, llm_provider_catalog: LLMProviderCatalogPort) -> None:
        self.llm_provider_catalog = llm_provider_catalog

    def execute(self) -> ListLLMProvidersResult:
        try:
            catalog = self.llm_provider_catalog.get_catalog()
        except (OSError, ValueError) as exc:
            return ListLLMProvidersResult(
                status=ListLLMProvidersStatus.ERROR,
                error=str(exc).strip() or "llm provider catalog query failed",
            )

        providers = tuple(
            LLMProviderItem(
                name=provider.name,
                source=catalog.source_for(provider.name),
                adapter=provider.adapter,
                enabled=provider.enabled,
                base_url=getattr(provider, "base_url", None),
                timeout_seconds=provider.timeout_seconds,
                credentials_file=getattr(provider, "credentials_file", None),
                profile=getattr(provider, "profile", None),
                api_key_file=_api_key_file_of(provider),
                models=tuple(
                    LLMProviderModelItem(
                        name=model.model,
                        context_window_tokens=model.context_window_tokens,
                    )
                    for model in provider.models
                ),
            )
            for provider in catalog.providers
            if provider.enabled
        )
        return ListLLMProvidersResult(
            status=ListLLMProvidersStatus.OK,
            providers=providers,
        )


def _api_key_file_of(provider: object) -> str | None:
    api_key_source = getattr(provider, "api_key_source", None)
    if api_key_source is None or api_key_source.type != LLMApiKeySourceType.FILE:
        return None
    return api_key_source.value
