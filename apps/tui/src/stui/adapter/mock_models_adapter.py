from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from stui.port.models_port import (
    MODEL_PROVIDER_SOURCE_NONE,
    MODEL_PROVIDER_SOURCES,
    ModelsPortModelItem,
    ModelsPortProviderItem,
)


def default_mock_models_path() -> Path:
    return Path(__file__).resolve().parents[1] / "mock" / "models.json"


@dataclass(frozen=True)
class MockModelsAdapter:
    path: Path = default_mock_models_path()

    def list_models(self, *, run_id: str) -> list[ModelsPortProviderItem]:
        _ = run_id
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise RuntimeError("models mock must contain a list")
        return [_parse_provider(item) for item in payload if isinstance(item, dict)]


def _parse_provider(payload: dict[str, Any]) -> ModelsPortProviderItem:
    models = payload.get("models", [])
    if not isinstance(models, list):
        models = []
    return ModelsPortProviderItem(
        name=str(payload.get("name", "")).strip(),
        source=_parse_source(payload),
        models=tuple(_parse_model(item) for item in models if isinstance(item, dict)),
    )


def _parse_source(payload: dict[str, Any]) -> str:
    source = str(payload.get("source", "")).strip()
    if source in MODEL_PROVIDER_SOURCES:
        return source
    return MODEL_PROVIDER_SOURCE_NONE


def _parse_model(payload: dict[str, Any]) -> ModelsPortModelItem:
    return ModelsPortModelItem(
        name=str(payload.get("name", "")).strip(),
        active=bool(payload.get("active", False)),
    )
