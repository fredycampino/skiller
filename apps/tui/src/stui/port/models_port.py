from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

MODEL_PROVIDER_SOURCE_DEFAULT = "default"
MODEL_PROVIDER_SOURCE_USER = "user"
MODEL_PROVIDER_SOURCE_ENV = "env"
MODEL_PROVIDER_SOURCE_NONE = "none"
# Legacy values are accepted when reading mock or older CLI payloads.
MODEL_PROVIDER_SOURCE_GLOBAL = "global"
MODEL_PROVIDER_SOURCE_LOCAL = "local"
MODEL_PROVIDER_SOURCES = frozenset(
    {
        MODEL_PROVIDER_SOURCE_DEFAULT,
        MODEL_PROVIDER_SOURCE_USER,
        MODEL_PROVIDER_SOURCE_ENV,
        MODEL_PROVIDER_SOURCE_NONE,
        MODEL_PROVIDER_SOURCE_GLOBAL,
        MODEL_PROVIDER_SOURCE_LOCAL,
    }
)


@dataclass(frozen=True)
class ModelsPortModelItem:
    name: str
    active: bool = False


@dataclass(frozen=True)
class ModelsPortProviderItem:
    name: str
    source: str
    models: tuple[ModelsPortModelItem, ...]


class ModelsPort(Protocol):
    def list_models(self, *, run_id: str) -> list[ModelsPortProviderItem]: ...

    def select_model(self, *, run_id: str, provider: str, model: str) -> None: ...
