import pytest

from skiller.domain.agent.llm.model import LLMToolChoiceMode
from skiller.domain.agent.llm.provider_catalog import (
    CodexLLMProviderDefinition,
    LLMModelDefinition,
    LLMProviderCatalog,
    OpenAILLMProviderDefinition,
)

pytestmark = pytest.mark.unit


def test_llm_provider_catalog_returns_provider_by_name() -> None:
    model = LLMModelDefinition(
        model="provider-model",
        context_window_tokens=128_000,
        max_output_tokens=None,
    )
    provider = OpenAILLMProviderDefinition(
        name="provider",
        timeout_seconds=30,
        models=(model,),
        enabled=True,
        base_url="https://provider.example/v1",
        temperature=1,
        top_p=1,
        parallel_tool_calls=True,
        tool_choice=LLMToolChoiceMode.AUTO,
        api_key_source=None,
        options={},
    )
    catalog = LLMProviderCatalog(providers=(provider,))

    assert catalog.get("provider") == provider


def test_llm_provider_catalog_rejects_duplicate_provider_names() -> None:
    model = LLMModelDefinition(
        model="provider-model",
        context_window_tokens=128_000,
        max_output_tokens=None,
    )
    provider = OpenAILLMProviderDefinition(
        name="provider",
        timeout_seconds=30,
        models=(model,),
        enabled=True,
        base_url="https://provider.example/v1",
        temperature=1,
        top_p=1,
        parallel_tool_calls=True,
        tool_choice=LLMToolChoiceMode.AUTO,
        api_key_source=None,
        options={},
    )

    with pytest.raises(
        ValueError,
        match="LLM provider catalog contains duplicate provider names",
    ):
        LLMProviderCatalog(providers=(provider, provider))


def test_codex_llm_provider_requires_credentials_file() -> None:
    model = LLMModelDefinition(
        model="gpt-5.6-sol",
        context_window_tokens=1_050_000,
        max_output_tokens=None,
    )

    with pytest.raises(ValueError, match="Codex LLM provider requires credentials_file"):
        CodexLLMProviderDefinition(
            name="codex",
            timeout_seconds=120,
            models=(model,),
            enabled=True,
            credentials_file="",
            parallel_tool_calls=True,
        )
