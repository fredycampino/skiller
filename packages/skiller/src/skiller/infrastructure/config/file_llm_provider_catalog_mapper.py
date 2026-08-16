from pydantic import ValidationError

from skiller.domain.agent.llm.model import LLMToolChoiceMode
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
from skiller.infrastructure.config.provider_catalog_schema import (
    LLMProviderCatalogSourceModel,
    LLMProviderConfigModel,
)

_OPENAI_FIELDS = frozenset(
    {
        "base_url",
        "temperature",
        "top_p",
        "parallel_tool_calls",
        "tool_choice",
        "api_key",
        "api_key_env",
        "api_key_file",
        "options",
    }
)
_CODEX_FIELDS = frozenset({"credentials_file"})
_OPENAI_INVALID_FIELDS = frozenset({"profile", "credentials_file"})
_CODEX_INVALID_FIELDS = (_OPENAI_FIELDS - {"parallel_tool_calls"}) | frozenset(
    {"profile", "max_output_tokens"}
)


class FileLLMProviderCatalogMapper:
    def to_provider_configs(
        self,
        raw_config: dict[str, object],
    ) -> tuple[LLMProviderConfigModel, ...]:
        try:
            source = LLMProviderCatalogSourceModel.model_validate(raw_config)
            providers = self._to_provider_configs(source)
        except ValidationError as exc:
            raise ValueError(f"Invalid LLM provider catalog: {exc}") from exc
        return providers

    def to_catalog(
        self,
        configs: tuple[LLMProviderConfigModel, ...],
    ) -> LLMProviderCatalog:
        providers = tuple(self._to_provider(config) for config in configs)
        return LLMProviderCatalog(providers=providers)

    def _to_provider_configs(
        self,
        source: LLMProviderCatalogSourceModel,
    ) -> tuple[LLMProviderConfigModel, ...]:
        providers: list[LLMProviderConfigModel] = []
        provider_names: set[str] = set()
        for raw_name, raw_provider in source.providers.items():
            name = raw_name.strip()
            if not name:
                raise ValueError("LLM provider name must not be empty")
            if name in provider_names:
                raise ValueError(f"Duplicate LLM provider name: {name}")
            if "name" in raw_provider:
                raise ValueError("LLM provider name must be declared as the map key")

            provider_names.add(name)
            provider = LLMProviderConfigModel.model_validate({"name": name, **raw_provider})
            providers.append(provider)
        return tuple(providers)

    def _to_provider(self, config: LLMProviderConfigModel) -> LLMProviderDefinition:
        if config.adapter is None:
            raise ValueError(f"LLM provider requires adapter: {config.name}")
        if config.timeout_seconds is None:
            raise ValueError(f"LLM provider requires timeout_seconds: {config.name}")
        if config.models is None:
            raise ValueError(f"LLM provider requires models: {config.name}")

        timeout_seconds = config.timeout_seconds
        models = tuple(
            LLMModelDefinition(
                model=model.model,
                context_window_tokens=model.context_window_tokens,
            )
            for model in config.models
        )
        if config.adapter == LLMAdapterType.OPENAI:
            return self._to_openai_provider(
                config=config,
                timeout_seconds=timeout_seconds,
                models=models,
            )
        if config.adapter == LLMAdapterType.BEDROCK:
            return self._to_bedrock_provider(
                config=config,
                timeout_seconds=timeout_seconds,
                models=models,
            )
        if config.adapter == LLMAdapterType.CODEX:
            return self._to_codex_provider(
                config=config,
                timeout_seconds=timeout_seconds,
                models=models,
            )
        raise ValueError(f"Unsupported LLM provider adapter: {config.adapter}")

    def _to_openai_provider(
        self,
        *,
        config: LLMProviderConfigModel,
        timeout_seconds: float,
        models: tuple[LLMModelDefinition, ...],
    ) -> OpenAILLMProviderDefinition:
        invalid_fields = sorted(config.model_fields_set & _OPENAI_INVALID_FIELDS)
        if invalid_fields:
            fields = ", ".join(invalid_fields)
            raise ValueError(f"OpenAI LLM provider does not accept fields: {config.name}: {fields}")
        if config.base_url is None:
            raise ValueError(f"LLM provider requires base_url: {config.name}")

        enabled = config.enabled if config.enabled is not None else True
        temperature = config.temperature if config.temperature is not None else 1
        top_p = config.top_p if config.top_p is not None else 1
        max_output_tokens = (
            config.max_output_tokens if config.max_output_tokens is not None else 4096
        )
        parallel_tool_calls = (
            config.parallel_tool_calls if config.parallel_tool_calls is not None else True
        )
        tool_choice = config.tool_choice or LLMToolChoiceMode.AUTO
        api_key_source = self._to_api_key_source(config)
        options = dict(config.options or {})

        return OpenAILLMProviderDefinition(
            name=config.name,
            timeout_seconds=timeout_seconds,
            models=models,
            enabled=enabled,
            base_url=config.base_url,
            temperature=temperature,
            top_p=top_p,
            max_output_tokens=max_output_tokens,
            parallel_tool_calls=parallel_tool_calls,
            tool_choice=tool_choice,
            api_key_source=api_key_source,
            options=options,
        )

    def _to_bedrock_provider(
        self,
        *,
        config: LLMProviderConfigModel,
        timeout_seconds: float,
        models: tuple[LLMModelDefinition, ...],
    ) -> BedrockLLMProviderDefinition:
        invalid_fields = sorted(config.model_fields_set & (_OPENAI_FIELDS | _CODEX_FIELDS))
        if invalid_fields:
            fields = ", ".join(invalid_fields)
            raise ValueError(
                f"Bedrock LLM provider does not accept fields: {config.name}: {fields}"
            )
        if config.profile is None:
            raise ValueError(f"LLM provider requires profile: {config.name}")

        enabled = config.enabled if config.enabled is not None else True
        max_output_tokens = (
            config.max_output_tokens if config.max_output_tokens is not None else 4096
        )
        return BedrockLLMProviderDefinition(
            name=config.name,
            timeout_seconds=timeout_seconds,
            models=models,
            enabled=enabled,
            profile=config.profile,
            max_output_tokens=max_output_tokens,
        )

    def _to_codex_provider(
        self,
        *,
        config: LLMProviderConfigModel,
        timeout_seconds: float,
        models: tuple[LLMModelDefinition, ...],
    ) -> CodexLLMProviderDefinition:
        invalid_fields = sorted(config.model_fields_set & _CODEX_INVALID_FIELDS)
        if invalid_fields:
            fields = ", ".join(invalid_fields)
            raise ValueError(f"Codex LLM provider does not accept fields: {config.name}: {fields}")
        if config.credentials_file is None:
            raise ValueError(f"LLM provider requires credentials_file: {config.name}")

        enabled = config.enabled if config.enabled is not None else True
        parallel_tool_calls = (
            config.parallel_tool_calls if config.parallel_tool_calls is not None else True
        )
        return CodexLLMProviderDefinition(
            name=config.name,
            timeout_seconds=timeout_seconds,
            models=models,
            enabled=enabled,
            credentials_file=config.credentials_file,
            parallel_tool_calls=parallel_tool_calls,
        )

    def _to_api_key_source(
        self,
        config: LLMProviderConfigModel,
    ) -> LLMApiKeySource | None:
        if config.api_key is not None:
            return LLMApiKeySource(
                type=LLMApiKeySourceType.VALUE,
                value=config.api_key,
            )
        if config.api_key_env is not None:
            return LLMApiKeySource(
                type=LLMApiKeySourceType.ENV,
                value=config.api_key_env,
            )
        if config.api_key_file is not None:
            return LLMApiKeySource(
                type=LLMApiKeySourceType.FILE,
                value=config.api_key_file,
            )
        return None
