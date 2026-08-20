from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from stui.port.models_port import (
    MODEL_PROVIDER_SOURCE_NONE,
    MODEL_PROVIDER_SOURCES,
    AuthProvidersPortModelItem,
    AuthProvidersPortProviderItem,
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
        payload = _load_payload(self.path)
        return [_parse_models_provider(item) for item in payload if isinstance(item, dict)]

    def list_providers(self) -> list[AuthProvidersPortProviderItem]:
        payload = _load_payload(self.path)
        return [_parse_auth_provider(item) for item in payload if isinstance(item, dict)]

    def select_model(self, *, run_id: str, provider: str, model: str) -> None:
        _ = run_id, provider, model


def _load_payload(path: Path) -> list[Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise RuntimeError("models mock must contain a list")
    return payload


def _parse_models_provider(payload: dict[str, Any]) -> ModelsPortProviderItem:
    models = payload.get("models", [])
    if not isinstance(models, list):
        models = []
    return ModelsPortProviderItem(
        name=str(payload.get("name", "")).strip(),
        source=_parse_source(payload),
        models=tuple(_parse_models_model(item) for item in models if isinstance(item, dict)),
    )


def _parse_models_model(payload: dict[str, Any]) -> ModelsPortModelItem:
    return ModelsPortModelItem(
        name=str(payload.get("name", "")).strip(),
        active=bool(payload.get("active", False)),
    )


def _parse_auth_provider(payload: dict[str, Any]) -> AuthProvidersPortProviderItem:
    models = payload.get("models", [])
    if not isinstance(models, list):
        models = []
    adapter = str(payload.get("adapter", "")).strip()
    if not adapter:
        raise RuntimeError("models mock provider missing adapter")
    return AuthProvidersPortProviderItem(
        name=str(payload.get("name", "")).strip(),
        source=_parse_source(payload),
        adapter=adapter,
        models=tuple(_parse_auth_model(item) for item in models if isinstance(item, dict)),
    )


def _parse_auth_model(payload: dict[str, Any]) -> AuthProvidersPortModelItem:
    context_window = payload.get("context_window_tokens", 0)
    if not isinstance(context_window, int):
        context_window = 0
    return AuthProvidersPortModelItem(
        name=str(payload.get("name", "")).strip(),
        context_window_tokens=context_window,
    )


def _parse_source(payload: dict[str, Any]) -> str:
    source = str(payload.get("source", "")).strip()
    if source in MODEL_PROVIDER_SOURCES:
        return source
    return MODEL_PROVIDER_SOURCE_NONE
