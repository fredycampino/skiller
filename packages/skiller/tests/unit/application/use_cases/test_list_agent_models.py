from pathlib import Path

import pytest
from helpers.agent_config import agent_config

from skiller.application.use_cases.agent.list_agent_models import (
    ListAgentModelsStatus,
    ListAgentModelsUseCase,
)
from skiller.domain.agent.llm.model import LLMToolChoiceMode
from skiller.domain.agent.llm.provider_catalog import (
    LLMModelDefinition,
    LLMProviderCatalog,
    LLMProviderCatalogSource,
    OpenAILLMProviderDefinition,
)
from skiller.domain.run.run_context_model import RunContext
from skiller.domain.run.run_model import Run

pytestmark = pytest.mark.unit


def test_list_agent_models_uses_catalog_and_marks_agent_selection() -> None:
    use_case = ListAgentModelsUseCase(
        run_store=_FakeRunStore(_run()),
        agent_config=_FakeAgentConfig(),
        llm_provider_catalog=_FakeCatalogPort(),
        skill_runner=_FakeSkillRunner(),
    )

    result = use_case.execute("run-1")

    assert result.status == ListAgentModelsStatus.OK
    assert [provider.name for provider in result.providers] == ["fake"]
    assert [model.name for model in result.providers[0].models] == ["model1", "model2"]
    assert [model.active for model in result.providers[0].models] == [True, False]
    assert result.providers[0].source == LLMProviderCatalogSource.DEFAULT


def test_list_agent_models_returns_run_not_found() -> None:
    result = ListAgentModelsUseCase(
        run_store=_FakeRunStore(None),
        agent_config=_FakeAgentConfig(),
        llm_provider_catalog=_FakeCatalogPort(),
        skill_runner=_FakeSkillRunner(),
    ).execute("missing")

    assert result.status == ListAgentModelsStatus.RUN_NOT_FOUND
    assert result.providers == ()


class _FakeRunStore:
    def __init__(self, run: Run | None) -> None:
        self.run = run

    def get_run(self, run_id: str) -> Run | None:
        _ = run_id
        return self.run


class _FakeAgentConfig:
    def get_config(self, *, config_path: Path | None = None):  # noqa: ANN201
        _ = config_path
        return agent_config()


class _FakeCatalogPort:
    def get_catalog(self) -> LLMProviderCatalog:
        models = (
            LLMModelDefinition(
                model="model1", context_window_tokens=100_000, max_output_tokens=None
            ),
            LLMModelDefinition(
                model="model2", context_window_tokens=100_000, max_output_tokens=None
            ),
        )
        provider = OpenAILLMProviderDefinition(
            name="fake",
            timeout_seconds=30,
            models=models,
            enabled=True,
            base_url="http://localhost/v1",
            temperature=0,
            top_p=1,
            parallel_tool_calls=True,
            tool_choice=LLMToolChoiceMode.AUTO,
            api_key_source=None,
            options={},
        )
        return LLMProviderCatalog(providers=(provider,))


class _FakeSkillRunner:
    def resolve_file_path(self, source: str, ref: str, file_ref: str) -> Path:
        _ = source, ref, file_ref
        raise FileNotFoundError


def _run() -> Run:
    return Run(
        id="run-1",
        source="internal",
        ref="demo",
        snapshot={"start": "agent", "steps": []},
        status="RUNNING",
        current="agent",
        context=RunContext(inputs={}, step_executions={}),
        created_at="2026-08-16T00:00:00Z",
        updated_at="2026-08-16T00:00:00Z",
    )
