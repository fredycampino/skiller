from pathlib import Path

import pytest

from skiller.domain.agent.llm.model import LLMToolChoiceMode
from skiller.domain.agent.llm.provider_catalog import (
    BedrockLLMProviderDefinition,
    LLMModelDefinition,
    LLMProviderCatalog,
    LLMProviderDefinition,
    OpenAILLMProviderDefinition,
)
from skiller.infrastructure.config.adapter_config import LLMProviderCatalogOverride
from skiller.infrastructure.config.file_llm_provider_catalog_datasource import (
    FileLLMProviderCatalogDatasource,
)
from skiller.infrastructure.config.file_llm_provider_catalog_mapper import (
    FileLLMProviderCatalogMapper,
)
from skiller.infrastructure.config.file_llm_provider_catalog_port import (
    FileLLMProviderCatalogPort,
)

pytestmark = pytest.mark.unit


class _FakeFileLLMProviderCatalogDatasource(FileLLMProviderCatalogDatasource):
    def __init__(
        self,
        providers_by_path: dict[Path, tuple[LLMProviderDefinition, ...]],
        overrides_by_path: dict[Path, tuple[LLMProviderCatalogOverride, ...]] | None = None,
    ) -> None:
        self.providers_by_path = providers_by_path
        self.overrides_by_path = overrides_by_path or {}
        self.calls: list[Path] = []

    def get_providers(self, path: Path) -> tuple[LLMProviderDefinition, ...]:
        self.calls.append(path)
        return self.providers_by_path[path]

    def get_override_providers(self, path: Path) -> tuple[LLMProviderCatalogOverride, ...]:
        self.calls.append(path)
        return self.overrides_by_path.get(path, ())


class _CapturingFileLLMProviderCatalogMapper(FileLLMProviderCatalogMapper):
    def __init__(self) -> None:
        self.configs: tuple[LLMProviderDefinition, ...] | None = None
        self.catalog: LLMProviderCatalog | None = None

    def to_catalog(
        self,
        configs: tuple[LLMProviderDefinition, ...],
    ) -> LLMProviderCatalog:
        self.configs = configs
        self.catalog = super().to_catalog(configs)
        return self.catalog


def test_port_merges_sources_by_precedence(monkeypatch: pytest.MonkeyPatch) -> None:
    default_path = Path("default.json")
    user_path = Path("user.json")
    env_path = Path("env.json")
    monkeypatch.setattr(Path, "exists", lambda path: path == user_path)
    default_provider = _openai_provider(
        timeout_seconds=30,
        temperature=1.0,
        models=(LLMModelDefinition(model="MiniMax-M2.5", context_window_tokens=204_800),),
        api_key_env="PROVIDER_API_KEY",
    )
    datasource = _FakeFileLLMProviderCatalogDatasource(
        providers_by_path={
            default_path: (default_provider,),
        },
        overrides_by_path={
            user_path: (
                LLMProviderCatalogOverride(
                    name="minimax",
                    fields={
                        "timeout_seconds": 60,
                        "models": (
                            {
                                "model": "MiniMax-M2.7",
                                "context_window_tokens": 204_800,
                            },
                        ),
                        "api_key_file": "/run/secrets/minimax",
                    },
                ),
            ),
            env_path: (
                LLMProviderCatalogOverride(
                    name="minimax",
                    fields={
                        "timeout_seconds": 90,
                        "temperature": 0.5,
                        "api_key_file": "/run/secrets/minimax",
                    },
                ),
            ),
        },
    )
    mapper = _CapturingFileLLMProviderCatalogMapper()
    port = FileLLMProviderCatalogPort(
        datasource=datasource,
        mapper=mapper,
        default_path=default_path,
        user_path=user_path,
        env={"AGENT_PROVIDERS_FILE": str(env_path)},
    )

    catalog = port.get_catalog()

    assert catalog is not None
    assert mapper.catalog is not None
    assert catalog.providers == mapper.catalog.providers
    assert datasource.calls == [default_path, user_path, env_path]
    assert mapper.configs is not None
    provider = mapper.configs[0]
    assert provider.timeout_seconds == 90
    assert provider.temperature == 0.5
    assert [model.model for model in provider.models] == ["MiniMax-M2.7"]
    assert provider.api_key_source is not None
    assert provider.api_key_source.value == "/run/secrets/minimax"
    assert catalog.source_for("minimax").value == "env"


def test_port_skips_missing_optional_user_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    default_path = Path("default.json")
    user_path = Path("missing-user.json")
    monkeypatch.setattr(Path, "exists", lambda path: False)
    datasource = _FakeFileLLMProviderCatalogDatasource(
        {
            default_path: (_openai_provider(),),
        }
    )
    mapper = _CapturingFileLLMProviderCatalogMapper()
    port = FileLLMProviderCatalogPort(
        datasource=datasource,
        mapper=mapper,
        default_path=default_path,
        user_path=user_path,
        env={},
    )

    catalog = port.get_catalog()

    assert datasource.calls == [default_path]
    assert catalog.source_for("minimax").value == "default"


def test_port_rejects_adapter_change(monkeypatch: pytest.MonkeyPatch) -> None:
    default_path = Path("default.json")
    user_path = Path("user.json")
    monkeypatch.setattr(Path, "exists", lambda path: path == user_path)
    datasource = _FakeFileLLMProviderCatalogDatasource(
        providers_by_path={
            default_path: (_openai_provider(),),
        },
        overrides_by_path={
            user_path: (
                LLMProviderCatalogOverride(
                    name="minimax",
                    fields={"adapter": "bedrock"},
                ),
            ),
        },
    )
    port = FileLLMProviderCatalogPort(
        datasource=datasource,
        mapper=_CapturingFileLLMProviderCatalogMapper(),
        default_path=default_path,
        user_path=user_path,
        env={},
    )

    with pytest.raises(ValueError, match="adapter cannot be changed: minimax"):
        port.get_catalog()


def _openai_provider(
    *,
    timeout_seconds: float = 30,
    temperature: float = 1.0,
    models: tuple[LLMModelDefinition, ...] = (
        LLMModelDefinition(model="MiniMax-M2.5", context_window_tokens=204_800),
    ),
    api_key_env: str | None = "PROVIDER_API_KEY",
    api_key_file: str | None = None,
) -> OpenAILLMProviderDefinition:
    from skiller.domain.agent.llm.provider_catalog import (
        LLMApiKeySource,
        LLMApiKeySourceType,
    )

    if api_key_file is not None:
        api_key_source = LLMApiKeySource(type=LLMApiKeySourceType.FILE, value=api_key_file)
    elif api_key_env is not None:
        api_key_source = LLMApiKeySource(type=LLMApiKeySourceType.ENV, value=api_key_env)
    else:
        api_key_source = LLMApiKeySource(type=LLMApiKeySourceType.VALUE, value="placeholder")
    return OpenAILLMProviderDefinition(
        name="minimax",
        timeout_seconds=timeout_seconds,
        models=models,
        enabled=True,
        base_url="https://provider.example/v1",
        temperature=temperature,
        top_p=1.0,
        max_output_tokens=4096,
        parallel_tool_calls=True,
        tool_choice=LLMToolChoiceMode.AUTO,
        api_key_source=api_key_source,
        options={},
    )


def _bedrock_provider() -> BedrockLLMProviderDefinition:
    return BedrockLLMProviderDefinition(
        name="minimax",
        timeout_seconds=45,
        models=(LLMModelDefinition(model="bedrock-model", context_window_tokens=200_000),),
        enabled=True,
        profile="default",
        max_output_tokens=4096,
    )
