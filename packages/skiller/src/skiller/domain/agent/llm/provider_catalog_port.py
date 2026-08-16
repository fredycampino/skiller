from typing import Protocol

from skiller.domain.agent.llm.provider_catalog import LLMProviderCatalog


class LLMProviderCatalogPort(Protocol):
    def get_catalog(self) -> LLMProviderCatalog: ...
