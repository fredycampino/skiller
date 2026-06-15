from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

MODEL_PROVIDER_SOURCE_GLOBAL = "global"
MODEL_PROVIDER_SOURCE_LOCAL = "local"
MODEL_PROVIDER_SOURCE_ENV = "env"
MODEL_PROVIDER_SOURCE_NONE = "none"
MODEL_PROVIDER_SOURCES = frozenset(
    {
        MODEL_PROVIDER_SOURCE_GLOBAL,
        MODEL_PROVIDER_SOURCE_LOCAL,
        MODEL_PROVIDER_SOURCE_ENV,
        MODEL_PROVIDER_SOURCE_NONE,
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
