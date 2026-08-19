from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Literal, Mapping, TypeAlias

from skiller.domain.agent.llm.model import LLMToolChoiceMode


class LLMAdapterType(str, Enum):
    OPENAI = "openai"
    BEDROCK = "bedrock"
    CODEX = "codex"


class LLMProviderCatalogSource(str, Enum):
    DEFAULT = "default"
    USER = "user"
    ENV = "env"


class LLMApiKeySourceType(str, Enum):
    VALUE = "value"
    ENV = "env"
    FILE = "file"


@dataclass(frozen=True)
class LLMApiKeySource:
    type: LLMApiKeySourceType
    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("LLM API key source requires value")


@dataclass(frozen=True)
class LLMModelDefinition:
    model: str
    context_window_tokens: int

    def __post_init__(self) -> None:
        if not self.model:
            raise ValueError("LLM model definition requires model")
        if self.context_window_tokens <= 0:
            raise ValueError("LLM model context window must be positive")

    @property
    def value(self) -> str:
        return self.model

    @property
    def model_context_window_tokens(self) -> int:
        return self.context_window_tokens


@dataclass(frozen=True)
class OpenAILLMProviderDefinition:
    name: str
    timeout_seconds: float
    models: tuple[LLMModelDefinition, ...]
    enabled: bool
    base_url: str
    temperature: float
    top_p: float
    max_output_tokens: int
    parallel_tool_calls: bool
    tool_choice: LLMToolChoiceMode
    api_key_source: LLMApiKeySource | None
    options: Mapping[str, object]
    adapter: Literal[LLMAdapterType.OPENAI] = field(
        default=LLMAdapterType.OPENAI,
        init=False,
    )

    def __post_init__(self) -> None:
        _validate_provider_definition(
            name=self.name,
            timeout_seconds=self.timeout_seconds,
            models=self.models,
        )
        if not self.base_url:
            raise ValueError("OpenAI LLM provider requires base_url")
        if self.temperature < 0:
            raise ValueError("OpenAI LLM provider temperature must not be negative")
        if self.top_p <= 0 or self.top_p > 1:
            raise ValueError("OpenAI LLM provider top_p must be greater than zero and at most one")
        if self.max_output_tokens <= 0:
            raise ValueError("OpenAI LLM provider max output tokens must be positive")
        object.__setattr__(self, "options", MappingProxyType(dict(self.options)))


@dataclass(frozen=True)
class BedrockLLMProviderDefinition:
    name: str
    timeout_seconds: float
    models: tuple[LLMModelDefinition, ...]
    enabled: bool
    profile: str
    max_output_tokens: int
    adapter: Literal[LLMAdapterType.BEDROCK] = field(
        default=LLMAdapterType.BEDROCK,
        init=False,
    )

    def __post_init__(self) -> None:
        _validate_provider_definition(
            name=self.name,
            timeout_seconds=self.timeout_seconds,
            models=self.models,
        )
        if not self.profile:
            raise ValueError("Bedrock LLM provider requires profile")
        if self.max_output_tokens <= 0:
            raise ValueError("Bedrock LLM provider max output tokens must be positive")


@dataclass(frozen=True)
class CodexLLMProviderDefinition:
    name: str
    timeout_seconds: float
    models: tuple[LLMModelDefinition, ...]
    enabled: bool
    credentials_file: str
    parallel_tool_calls: bool
    max_output_tokens: int
    adapter: Literal[LLMAdapterType.CODEX] = field(
        default=LLMAdapterType.CODEX,
        init=False,
    )

    def __post_init__(self) -> None:
        _validate_provider_definition(
            name=self.name,
            timeout_seconds=self.timeout_seconds,
            models=self.models,
        )
        if not self.credentials_file:
            raise ValueError("Codex LLM provider requires credentials_file")
        if self.max_output_tokens <= 0:
            raise ValueError("Codex LLM provider max output tokens must be positive")


LLMProviderDefinition: TypeAlias = (
    OpenAILLMProviderDefinition | BedrockLLMProviderDefinition | CodexLLMProviderDefinition
)


@dataclass(frozen=True)
class LLMProviderCatalog:
    providers: tuple[LLMProviderDefinition, ...]
    sources: Mapping[str, LLMProviderCatalogSource] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.providers:
            raise ValueError("LLM provider catalog must not be empty")
        provider_names = [provider.name for provider in self.providers]
        if len(provider_names) != len(set(provider_names)):
            raise ValueError("LLM provider catalog contains duplicate provider names")
        unknown_sources = set(self.sources) - set(provider_names)
        if unknown_sources:
            names = ", ".join(sorted(unknown_sources))
            raise ValueError(f"LLM provider catalog contains unknown sources: {names}")
        sources = {
            provider.name: self.sources.get(
                provider.name,
                LLMProviderCatalogSource.DEFAULT,
            )
            for provider in self.providers
        }
        object.__setattr__(self, "sources", MappingProxyType(sources))

    def get(self, name: str) -> LLMProviderDefinition:
        for provider in self.providers:
            if provider.name == name:
                return provider
        raise ValueError(f"Unsupported LLM provider: {name}")

    def get_model(self, *, provider_name: str, model_name: str) -> LLMModelDefinition:
        provider = self.get(provider_name)
        for model in provider.models:
            if model.model == model_name:
                return model
        raise ValueError(f"Unsupported model='{model_name}' for provider='{provider_name}'")

    def source_for(self, provider_name: str) -> LLMProviderCatalogSource:
        self.get(provider_name)
        return self.sources[provider_name]


def _validate_provider_definition(
    *,
    name: str,
    timeout_seconds: float,
    models: tuple[LLMModelDefinition, ...],
) -> None:
    if not name:
        raise ValueError("LLM provider definition requires name")
    if timeout_seconds <= 0:
        raise ValueError("LLM provider timeout must be positive")
    if not models:
        raise ValueError("LLM provider models must not be empty")
    model_names = [model.model for model in models]
    if len(model_names) != len(set(model_names)):
        raise ValueError(f"LLM provider contains duplicate models: {name}")
