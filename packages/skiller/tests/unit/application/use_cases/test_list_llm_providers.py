import pytest

from skiller.application.use_cases.agent.list_llm_providers import (
    ListLLMProvidersStatus,
    ListLLMProvidersUseCase,
)
from skiller.domain.agent.llm.model import LLMToolChoiceMode
from skiller.domain.agent.llm.provider_catalog import (
    LLMAdapterType,
    LLMApiKeySource,
    LLMApiKeySourceType,
    LLMModelDefinition,
    LLMProviderCatalog,
    LLMProviderCatalogSource,
    OpenAILLMProviderDefinition,
)

pytestmark = pytest.mark.unit


def test_list_llm_providers_returns_enabled_providers_with_sources() -> None:
    use_case = ListLLMProvidersUseCase(llm_provider_catalog=_FakeCatalogPort())

    result = use_case.execute()

    assert result.status == ListLLMProvidersStatus.OK
    assert result.error is None
    assert [provider.name for provider in result.providers] == ["moonshot", "codex"]
    moonshot = result.providers[0]
    assert moonshot.source == LLMProviderCatalogSource.USER
    assert moonshot.adapter == LLMAdapterType.OPENAI
    assert moonshot.enabled is True
    assert moonshot.base_url == "http://localhost/v1"
    assert moonshot.timeout_seconds == 30
    assert moonshot.credentials_file is None
    assert moonshot.profile is None
    assert moonshot.api_key_file == "~/.skiller/secrets/moonshot_api_key"
    assert [(model.name, model.context_window_tokens) for model in moonshot.models] == [
        ("kimi-k2", 262_144),
    ]
    codex = result.providers[1]
    assert codex.source == LLMProviderCatalogSource.DEFAULT


def test_list_llm_providers_skips_disabled_providers() -> None:
    use_case = ListLLMProvidersUseCase(
        llm_provider_catalog=_FakeCatalogPort(enabled_by_name={"moonshot": True, "codex": False}),
    )

    result = use_case.execute()

    assert result.status == ListLLMProvidersStatus.OK
    assert [provider.name for provider in result.providers] == ["moonshot"]


def test_list_llm_providers_reports_catalog_error() -> None:
    use_case = ListLLMProvidersUseCase(llm_provider_catalog=_FailingCatalogPort())

    result = use_case.execute()

    assert result.status == ListLLMProvidersStatus.ERROR
    assert result.providers == ()
    assert result.error == "catalog unreadable"


class _FakeCatalogPort:
    def __init__(self, enabled_by_name: dict[str, bool] | None = None) -> None:
        self.enabled_by_name = enabled_by_name or {}

    def get_catalog(self) -> LLMProviderCatalog:
        providers = (
            _provider(name="moonshot", enabled=self.enabled_by_name.get("moonshot", True)),
            _provider(name="codex", enabled=self.enabled_by_name.get("codex", True)),
        )
        return LLMProviderCatalog(
            providers=providers,
            sources={
                "moonshot": LLMProviderCatalogSource.USER,
                "codex": LLMProviderCatalogSource.DEFAULT,
            },
        )


class _FailingCatalogPort:
    def get_catalog(self) -> LLMProviderCatalog:
        raise ValueError("catalog unreadable")


def _provider(*, name: str, enabled: bool = True) -> OpenAILLMProviderDefinition:
    return OpenAILLMProviderDefinition(
        name=name,
        timeout_seconds=30,
        models=(LLMModelDefinition(model="kimi-k2", context_window_tokens=262_144),),
        enabled=enabled,
        base_url="http://localhost/v1",
        temperature=0,
        top_p=1,
        max_output_tokens=1024,
        parallel_tool_calls=False,
        tool_choice=LLMToolChoiceMode.AUTO,
        api_key_source=LLMApiKeySource(
            type=LLMApiKeySourceType.FILE,
            value="~/.skiller/secrets/moonshot_api_key",
        ),
        options={},
    )
