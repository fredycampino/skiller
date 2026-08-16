from pathlib import Path

import pytest

from skiller.domain.agent.llm.provider_catalog import (
    LLMAdapterType,
    LLMProviderCatalog,
)
from skiller.infrastructure.config.file_llm_provider_catalog_datasource import (
    FileLLMProviderCatalogDatasource,
)
from skiller.infrastructure.config.file_llm_provider_catalog_mapper import (
    FileLLMProviderCatalogMapper,
)
from skiller.infrastructure.config.file_llm_provider_catalog_port import (
    FileLLMProviderCatalogPort,
)
from skiller.infrastructure.config.provider_catalog_schema import (
    LLMModelConfigModel,
    LLMProviderConfigModel,
)

pytestmark = pytest.mark.unit


class _FakeFileLLMProviderCatalogDatasource(FileLLMProviderCatalogDatasource):
    def __init__(
        self,
        providers_by_path: dict[Path, tuple[LLMProviderConfigModel, ...]],
    ) -> None:
        self.providers_by_path = providers_by_path
        self.calls: list[Path] = []

    def get_providers(self, path: Path) -> tuple[LLMProviderConfigModel, ...]:
        self.calls.append(path)
        return self.providers_by_path[path]


class _CapturingFileLLMProviderCatalogMapper(FileLLMProviderCatalogMapper):
    def __init__(self) -> None:
        self.configs: tuple[LLMProviderConfigModel, ...] | None = None
        self.catalog: LLMProviderCatalog | None = None

    def to_catalog(
        self,
        configs: tuple[LLMProviderConfigModel, ...],
    ) -> LLMProviderCatalog:
        self.configs = configs
        self.catalog = super().to_catalog(configs)
        return self.catalog


def test_port_merges_sources_by_precedence(monkeypatch: pytest.MonkeyPatch) -> None:
    default_path = Path("default.json")
    user_path = Path("user.json")
    env_path = Path("env.json")
    monkeypatch.setattr(Path, "exists", lambda path: path == user_path)
    default_provider = _provider(
        adapter=LLMAdapterType.OPENAI,
        base_url="https://provider.example/v1",
        api_key_env="PROVIDER_API_KEY",
        timeout_seconds=30,
        models=(_model("MiniMax-M2.5"),),
    )
    user_provider = _provider(
        timeout_seconds=60,
        models=(_model("MiniMax-M2.7"),),
        api_key_file="/run/secrets/minimax",
    )
    env_provider = _provider(timeout_seconds=90, temperature=0.5)
    datasource = _FakeFileLLMProviderCatalogDatasource(
        {
            default_path: (default_provider,),
            user_path: (user_provider,),
            env_path: (env_provider,),
        }
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
    assert provider.models is not None
    assert [model.model for model in provider.models] == ["MiniMax-M2.7"]
    assert provider.api_key_env is None
    assert provider.api_key_file == "/run/secrets/minimax"
    assert catalog.source_for("minimax").value == "env"


def test_port_skips_missing_optional_user_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    default_path = Path("default.json")
    user_path = Path("missing-user.json")
    monkeypatch.setattr(Path, "exists", lambda path: False)
    datasource = _FakeFileLLMProviderCatalogDatasource(
        {
            default_path: (
                _provider(
                    adapter=LLMAdapterType.OPENAI,
                    base_url="https://provider.example/v1",
                    timeout_seconds=30,
                    models=(_model("MiniMax-M2.5"),),
                ),
            ),
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
        {
            default_path: (_provider(adapter=LLMAdapterType.OPENAI),),
            user_path: (_provider(adapter=LLMAdapterType.BEDROCK),),
        }
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


def _provider(
    **fields: object,
) -> LLMProviderConfigModel:
    values: dict[str, object] = {"name": "minimax"}
    values.update(fields)
    return LLMProviderConfigModel.model_validate(values)


def _model(model: str) -> LLMModelConfigModel:
    return LLMModelConfigModel(
        model=model,
        context_window_tokens=204_800,
    )
