"""Adapter-specific configuration models for the LLM provider catalog.

Each LLM provider adapter declares its own configuration model with all
required fields. Defaults are intentionally absent: every value must be
present in the catalog JSON. This makes the JSON explicit and avoids
silent fallback values in code.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Annotated, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from skiller.domain.agent.llm.model import LLMToolChoiceMode
from skiller.domain.agent.llm.provider_catalog import LLMAdapterType


class LLMModelConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    model: str = Field(min_length=1)
    context_window_tokens: int = Field(gt=0)

    @field_validator("model")
    @classmethod
    def normalize_model(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("LLM model must not be empty")
        return normalized


class _LLMAdapterConfigModelBase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    enabled: bool
    timeout_seconds: float = Field(gt=0)
    models: tuple[LLMModelConfigModel, ...] = Field(min_length=1)
    max_output_tokens: int = Field(gt=0)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("LLM provider name must not be empty")
        return normalized


class _LLMAdapterOverrideModelBase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    enabled: bool | None = None
    timeout_seconds: float | None = Field(default=None, gt=0)
    models: tuple[LLMModelConfigModel, ...] | None = Field(default=None, min_length=1)
    max_output_tokens: int | None = Field(default=None, gt=0)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("LLM provider name must not be empty")
        return normalized


class BedrockAdapterConfigModel(_LLMAdapterConfigModelBase):
    adapter: Literal[LLMAdapterType.BEDROCK] = LLMAdapterType.BEDROCK
    profile: str = Field(min_length=1)

    @field_validator("profile")
    @classmethod
    def normalize_profile(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Bedrock LLM provider profile must not be empty")
        return normalized


class OpenAIAdapterConfigModel(_LLMAdapterConfigModelBase):
    adapter: Literal[LLMAdapterType.OPENAI] = LLMAdapterType.OPENAI
    base_url: str = Field(min_length=1)
    temperature: float = Field(ge=0)
    top_p: float = Field(gt=0, le=1)
    parallel_tool_calls: bool
    tool_choice: LLMToolChoiceMode
    api_key: str | None = Field(default=None, min_length=1)
    api_key_env: str | None = Field(default=None, min_length=1)
    api_key_file: str | None = Field(default=None, min_length=1)
    options: dict[str, object] = Field(default_factory=dict)

    @field_validator("base_url", "api_key", "api_key_env", "api_key_file")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("OpenAI LLM provider text fields must not be empty")
        return normalized

    @model_validator(mode="after")
    def validate_api_key_source(self) -> "OpenAIAdapterConfigModel":
        sources = (self.api_key, self.api_key_env, self.api_key_file)
        if sum(source is not None for source in sources) > 1:
            raise ValueError("OpenAI LLM provider accepts only one api_key source")
        if all(source is None for source in sources):
            raise ValueError("OpenAI LLM provider requires an api_key source")
        return self


class CodexAdapterConfigModel(_LLMAdapterConfigModelBase):
    adapter: Literal[LLMAdapterType.CODEX] = LLMAdapterType.CODEX
    credentials_file: str = Field(min_length=1)
    parallel_tool_calls: bool

    @field_validator("credentials_file")
    @classmethod
    def normalize_credentials_file(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Codex LLM provider credentials_file must not be empty")
        return normalized


class BedrockAdapterOverrideModel(_LLMAdapterOverrideModelBase):
    profile: str | None = Field(default=None, min_length=1)

    @field_validator("profile")
    @classmethod
    def normalize_profile(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("Bedrock LLM provider profile must not be empty")
        return normalized


class OpenAIAdapterOverrideModel(_LLMAdapterOverrideModelBase):
    base_url: str | None = Field(default=None, min_length=1)
    temperature: float | None = Field(default=None, ge=0)
    top_p: float | None = Field(default=None, gt=0, le=1)
    parallel_tool_calls: bool | None = None
    tool_choice: LLMToolChoiceMode | None = None
    api_key: str | None = Field(default=None, min_length=1)
    api_key_env: str | None = Field(default=None, min_length=1)
    api_key_file: str | None = Field(default=None, min_length=1)
    options: dict[str, object] | None = None

    @field_validator("base_url", "api_key", "api_key_env", "api_key_file")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("OpenAI LLM provider text fields must not be empty")
        return normalized

    @model_validator(mode="after")
    def validate_api_key_source(self) -> "OpenAIAdapterOverrideModel":
        sources = (self.api_key, self.api_key_env, self.api_key_file)
        if sum(source is not None for source in sources) > 1:
            raise ValueError("OpenAI LLM provider accepts only one api_key source")
        return self


class CodexAdapterOverrideModel(_LLMAdapterOverrideModelBase):
    credentials_file: str | None = Field(default=None, min_length=1)
    parallel_tool_calls: bool | None = None

    @field_validator("credentials_file")
    @classmethod
    def normalize_credentials_file(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("Codex LLM provider credentials_file must not be empty")
        return normalized


LLMAdapterConfigModel = Annotated[
    BedrockAdapterConfigModel | OpenAIAdapterConfigModel | CodexAdapterConfigModel,
    Field(discriminator="adapter"),
]


class LLMProviderCatalogOverrideModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    adapter: LLMAdapterType | None = None
    enabled: bool | None = None
    timeout_seconds: float | None = Field(default=None, gt=0)
    models: tuple[LLMModelConfigModel, ...] | None = Field(default=None, min_length=1)
    max_output_tokens: int | None = Field(default=None, gt=0)
    profile: str | None = Field(default=None, min_length=1)
    credentials_file: str | None = Field(default=None, min_length=1)
    base_url: str | None = Field(default=None, min_length=1)
    temperature: float | None = Field(default=None, ge=0)
    top_p: float | None = Field(default=None, gt=0, le=1)
    parallel_tool_calls: bool | None = None
    tool_choice: LLMToolChoiceMode | None = None
    api_key: str | None = Field(default=None, min_length=1)
    api_key_env: str | None = Field(default=None, min_length=1)
    api_key_file: str | None = Field(default=None, min_length=1)
    options: dict[str, object] | None = None

    @model_validator(mode="before")
    @classmethod
    def reject_explicit_nulls(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        null_fields = sorted(key for key, item in value.items() if item is None)
        if null_fields:
            fields = ", ".join(null_fields)
            raise ValueError(f"LLM provider override fields must not be null: {fields}")
        return value

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("LLM provider name must not be empty")
        return normalized

    @field_validator(
        "profile", "credentials_file", "base_url", "api_key", "api_key_env", "api_key_file"
    )
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("LLM provider text fields must not be empty")
        return normalized


@dataclass(frozen=True)
class LLMProviderCatalogOverride:
    name: str
    fields: Mapping[str, object]

    def __post_init__(self) -> None:
        object.__setattr__(self, "fields", MappingProxyType(dict(self.fields)))


class LLMProviderCatalogOverrideSourceModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    providers: dict[str, LLMProviderCatalogOverrideModel]

    @model_validator(mode="before")
    @classmethod
    def inject_provider_name(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        providers = value.get("providers")
        if not isinstance(providers, dict):
            return value
        injected: dict[str, object] = {}
        for raw_name, raw_provider in providers.items():
            if not isinstance(raw_provider, dict):
                injected[raw_name] = raw_provider
                continue
            if "name" in raw_provider:
                raise ValueError(
                    "LLM provider name must be declared as the map key, not inside the entry",
                )
            injected[raw_name] = {"name": raw_name, **raw_provider}
        return {"providers": injected}


class LLMProviderCatalogSourceModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    providers: dict[str, LLMAdapterConfigModel]

    @model_validator(mode="before")
    @classmethod
    def inject_provider_name(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        providers = value.get("providers")
        if not isinstance(providers, dict):
            return value
        injected: dict[str, object] = {}
        for raw_name, raw_provider in providers.items():
            if not isinstance(raw_provider, dict):
                injected[raw_name] = raw_provider
                continue
            if "name" in raw_provider:
                raise ValueError(
                    "LLM provider name must be declared as the map key, not inside the entry",
                )
            injected[raw_name] = {"name": raw_name, **raw_provider}
        return {"providers": injected}
