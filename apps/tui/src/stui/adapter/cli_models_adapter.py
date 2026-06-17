from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from stui.adapter.cli_invoker import CliInvoker
from stui.port.models_port import (
    MODEL_PROVIDER_SOURCE_NONE,
    MODEL_PROVIDER_SOURCES,
    ModelsPortModelItem,
    ModelsPortProviderItem,
)


@dataclass(frozen=True)
class CliModelsAdapter:
    invoker: CliInvoker = field(default_factory=CliInvoker)

    def list_models(self, *, run_id: str) -> list[ModelsPortProviderItem]:
        normalized_run_id = run_id.strip()
        if not normalized_run_id:
            raise RuntimeError("models command requires run_id")

        payload = _run_json_command(
            self.invoker,
            "agent",
            "models",
            normalized_run_id,
        )
        if not isinstance(payload, dict):
            raise RuntimeError("models command returned invalid payload")
        if payload.get("ok") is not True:
            raise RuntimeError(_error_message(payload))

        providers = payload.get("providers")
        if not isinstance(providers, list):
            raise RuntimeError("models command returned invalid providers")
        return [_parse_provider(item) for item in providers if isinstance(item, dict)]

    def select_model(self, *, run_id: str, provider: str, model: str) -> None:
        payload = _run_json_command(
            self.invoker,
            "agent",
            "model",
            run_id,
            "--provider",
            provider,
            "--model",
            model,
        )
        if not isinstance(payload, dict):
            raise RuntimeError("model command returned invalid payload")
        if payload.get("ok") is not True:
            raise RuntimeError(_error_message(payload, fallback="model selection failed"))


def _run_json_command(invoker: CliInvoker, *args: str) -> Any:
    completed = invoker.run(*args)

    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "runtime command failed"
        raise RuntimeError(detail)

    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("runtime command returned invalid JSON") from exc


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


def _error_message(payload: dict[str, Any], *, fallback: str = "models query failed") -> str:
    message = str(payload.get("message", "")).strip()
    if message:
        return message
    error = str(payload.get("error", "")).strip()
    if error:
        return error
    status = str(payload.get("status", "")).strip()
    if status:
        return f"{fallback}: {status}"
    return fallback
