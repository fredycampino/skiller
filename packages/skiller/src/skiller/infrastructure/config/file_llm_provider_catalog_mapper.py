"""File-backed LLM provider catalog mapper.

Parses the user JSON catalog into typed adapter config models and converts
each entry into the corresponding domain-level LLM provider definition.

The mapper is intentionally free of default values: every adapter model
declares its full configuration, and the user JSON must be exhaustively
defined. Defaults would silently shadow the JSON and reintroduce the bug
class that motivated this refactor.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any, TypeVar

from pydantic import ValidationError

from skiller.domain.agent.llm.provider_catalog import (
    BedrockLLMProviderDefinition,
    CodexLLMProviderDefinition,
    LLMAdapterType,
    LLMApiKeySource,
    LLMApiKeySourceType,
    LLMModelDefinition,
    LLMProviderCatalog,
    LLMProviderDefinition,
    OpenAILLMProviderDefinition,
)
from skiller.infrastructure.config.adapter_config import (
    BedrockAdapterConfigModel,
    BedrockAdapterOverrideModel,
    CodexAdapterConfigModel,
    CodexAdapterOverrideModel,
    LLMAdapterConfigModel,
    LLMModelConfigModel,
    LLMProviderCatalogOverride,
    LLMProviderCatalogOverrideSourceModel,
    LLMProviderCatalogSourceModel,
    OpenAIAdapterConfigModel,
    OpenAIAdapterOverrideModel,
)

_OverrideModel = TypeVar("_OverrideModel")


class FileLLMProviderCatalogMapper:
    def to_provider_configs(
        self,
        raw_config: dict[str, Any] | Path,
    ) -> tuple[LLMProviderDefinition, ...]:
        if isinstance(raw_config, Path):
            raw_config = json.loads(raw_config.read_text())
        try:
            source = LLMProviderCatalogSourceModel.model_validate(raw_config)
        except ValidationError as exc:
            raise ValueError(f"Invalid LLM provider catalog: {exc}") from exc
        return tuple(self._to_provider_config(entry) for entry in source.providers.values())

    def to_override_configs(
        self,
        raw_config: dict[str, Any] | Path,
    ) -> tuple[LLMProviderCatalogOverride, ...]:
        if isinstance(raw_config, Path):
            raw_config = json.loads(raw_config.read_text())
        try:
            source = LLMProviderCatalogOverrideSourceModel.model_validate(raw_config)
        except ValidationError as exc:
            raise ValueError(f"Invalid LLM provider catalog override: {exc}") from exc
        return tuple(
            _to_catalog_override(entry_name=entry.name, entry_fields=entry.model_dump())
            for entry in source.providers.values()
        )

    def to_new_provider(
        self,
        override: LLMProviderCatalogOverride,
    ) -> LLMProviderDefinition:
        raw_config = {"providers": {override.name: dict(override.fields)}}
        providers = self.to_provider_configs(raw_config)
        return providers[0]

    def apply_override(
        self,
        *,
        base: LLMProviderDefinition,
        override: LLMProviderCatalogOverride,
    ) -> LLMProviderDefinition:
        if "adapter" in override.fields:
            raise ValueError(f"LLM provider adapter cannot be changed: {base.name}")
        raw_override = {"name": override.name, **override.fields}
        if isinstance(base, OpenAILLMProviderDefinition):
            config = _validate_override(OpenAIAdapterOverrideModel, raw_override)
            updates = _to_openai_override_updates(config)
            return dataclasses.replace(base, **updates)
        if isinstance(base, BedrockLLMProviderDefinition):
            config = _validate_override(BedrockAdapterOverrideModel, raw_override)
            updates = _to_provider_override_updates(config)
            return dataclasses.replace(base, **updates)
        if isinstance(base, CodexLLMProviderDefinition):
            config = _validate_override(CodexAdapterOverrideModel, raw_override)
            updates = _to_provider_override_updates(config)
            return dataclasses.replace(base, **updates)
        raise ValueError(f"Unsupported LLM provider adapter: {base.adapter}")

    def to_catalog(
        self,
        base: tuple[LLMProviderDefinition, ...],
    ) -> LLMProviderCatalog:
        return LLMProviderCatalog(providers=base)

    @staticmethod
    def _to_provider_config(entry: LLMAdapterConfigModel) -> LLMProviderDefinition:
        match entry.adapter:
            case LLMAdapterType.BEDROCK:
                return FileLLMProviderCatalogMapper._to_bedrock_provider(entry)
            case LLMAdapterType.OPENAI:
                return FileLLMProviderCatalogMapper._to_openai_provider(entry)
            case LLMAdapterType.CODEX:
                return FileLLMProviderCatalogMapper._to_codex_provider(entry)

    @staticmethod
    def _to_bedrock_provider(config: BedrockAdapterConfigModel) -> LLMProviderDefinition:
        models = tuple(
            LLMModelDefinition(
                model=m.model,
                context_window_tokens=m.context_window_tokens,
                max_output_tokens=m.max_output_tokens,
            )
            for m in config.models
        )
        return BedrockLLMProviderDefinition(
            name=config.name,
            enabled=config.enabled,
            timeout_seconds=config.timeout_seconds,
            models=models,
            profile=config.profile,
        )

    @staticmethod
    def _to_openai_provider(config: OpenAIAdapterConfigModel) -> LLMProviderDefinition:
        models = tuple(
            LLMModelDefinition(
                model=m.model,
                context_window_tokens=m.context_window_tokens,
                max_output_tokens=m.max_output_tokens,
            )
            for m in config.models
        )
        api_key_source = _resolve_openai_api_key_source(config)
        return OpenAILLMProviderDefinition(
            name=config.name,
            enabled=config.enabled,
            timeout_seconds=config.timeout_seconds,
            models=models,
            base_url=config.base_url,
            temperature=config.temperature,
            top_p=config.top_p,
            parallel_tool_calls=config.parallel_tool_calls,
            tool_choice=config.tool_choice,
            api_key_source=api_key_source,
            options=dict(config.options),
        )

    @staticmethod
    def _to_codex_provider(config: CodexAdapterConfigModel) -> LLMProviderDefinition:
        models = tuple(
            LLMModelDefinition(
                model=m.model,
                context_window_tokens=m.context_window_tokens,
                max_output_tokens=m.max_output_tokens,
            )
            for m in config.models
        )
        return CodexLLMProviderDefinition(
            name=config.name,
            enabled=config.enabled,
            timeout_seconds=config.timeout_seconds,
            models=models,
            credentials_file=config.credentials_file,
            parallel_tool_calls=config.parallel_tool_calls,
        )


def _resolve_openai_api_key_source(config: OpenAIAdapterConfigModel) -> LLMApiKeySource:
    if config.api_key is not None:
        return LLMApiKeySource(type=LLMApiKeySourceType.VALUE, value=config.api_key)
    if config.api_key_env is not None:
        return LLMApiKeySource(type=LLMApiKeySourceType.ENV, value=config.api_key_env)
    return LLMApiKeySource(type=LLMApiKeySourceType.FILE, value=config.api_key_file)


def _to_catalog_override(
    *,
    entry_name: str,
    entry_fields: dict[str, Any],
) -> LLMProviderCatalogOverride:
    fields = {
        key: value for key, value in entry_fields.items() if value is not None and key != "name"
    }
    return LLMProviderCatalogOverride(name=entry_name, fields=fields)


def _validate_override(
    model: type[_OverrideModel],
    raw_override: dict[str, object],
) -> _OverrideModel:
    try:
        return model.model_validate(raw_override)  # type: ignore[attr-defined]
    except ValidationError as exc:
        raise ValueError(f"Invalid LLM provider catalog override: {exc}") from exc


def _to_provider_override_updates(
    config: BedrockAdapterOverrideModel | CodexAdapterOverrideModel | OpenAIAdapterOverrideModel,
) -> dict[str, object]:
    values = config.model_dump(exclude_none=True)
    values.pop("name")
    if config.models is not None:
        values["models"] = _to_model_definitions(config.models)
    return values


def _to_openai_override_updates(config: OpenAIAdapterOverrideModel) -> dict[str, object]:
    values = _to_provider_override_updates(config)
    api_key_fields = {"api_key", "api_key_env", "api_key_file"}
    if not api_key_fields & set(values):
        return values
    api_key = values.pop("api_key", None)
    api_key_env = values.pop("api_key_env", None)
    api_key_file = values.pop("api_key_file", None)
    if api_key is not None:
        values["api_key_source"] = LLMApiKeySource(
            type=LLMApiKeySourceType.VALUE,
            value=api_key,
        )
        return values
    if api_key_env is not None:
        values["api_key_source"] = LLMApiKeySource(
            type=LLMApiKeySourceType.ENV,
            value=api_key_env,
        )
        return values
    values["api_key_source"] = LLMApiKeySource(
        type=LLMApiKeySourceType.FILE,
        value=api_key_file,
    )
    return values


def _to_model_definitions(
    models: tuple[LLMModelConfigModel, ...],
) -> tuple[LLMModelDefinition, ...]:
    return tuple(
        LLMModelDefinition(
            model=model.model,
            context_window_tokens=model.context_window_tokens,
            max_output_tokens=model.max_output_tokens,
        )
        for model in models
    )
