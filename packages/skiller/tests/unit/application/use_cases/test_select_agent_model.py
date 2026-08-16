from pathlib import Path

import pytest

from skiller.application.use_cases.agent.select_agent_model import (
    SelectAgentModelStatus,
    SelectAgentModelUseCase,
)
from skiller.domain.agent.llm.model import LLMToolChoiceMode
from skiller.domain.agent.llm.provider_catalog import (
    LLMModelDefinition,
    LLMProviderCatalog,
    OpenAILLMProviderDefinition,
)
from skiller.domain.event.event_model import (
    RunModelUpdatedPayload,
    RuntimeEvent,
    RuntimeEventDraft,
    RuntimeEventType,
)
from skiller.domain.run.run_context_model import RunContext
from skiller.domain.run.run_model import Run

pytestmark = pytest.mark.unit


def test_select_agent_model_persists_catalog_selection() -> None:
    agent_config = _FakeAgentConfig()
    events = _FakeRuntimeEventStore()
    use_case = _use_case(run=_run(), agent_config=agent_config, events=events)

    result = use_case.execute(run_id="run-1", provider="fake", model="model2")

    assert result.status == SelectAgentModelStatus.OK
    assert agent_config.selections == [("fake", "model2", None)]
    assert len(events.events) == 1
    assert events.events[0].type == RuntimeEventType.RUN_MODEL_UPDATED
    assert events.events[0].run_id == "run-1"
    assert events.events[0].payload == RunModelUpdatedPayload(
        provider="fake",
        model="model2",
    )


@pytest.mark.parametrize(
    ("provider", "model", "status"),
    [
        ("missing", "model1", SelectAgentModelStatus.PROVIDER_NOT_SUPPORTED),
        ("fake", "missing", SelectAgentModelStatus.MODEL_NOT_SUPPORTED),
    ],
)
def test_select_agent_model_rejects_unknown_catalog_selection(
    provider: str,
    model: str,
    status: SelectAgentModelStatus,
) -> None:
    result = _use_case(run=_run()).execute(
        run_id="run-1",
        provider=provider,
        model=model,
    )

    assert result.status == status


def test_select_agent_model_returns_run_not_found() -> None:
    result = _use_case(run=None).execute(
        run_id="missing",
        provider="fake",
        model="model1",
    )

    assert result.status == SelectAgentModelStatus.RUN_NOT_FOUND


def _use_case(
    *,
    run: Run | None,
    agent_config: "_FakeAgentConfig | None" = None,
    events: "_FakeRuntimeEventStore | None" = None,
) -> SelectAgentModelUseCase:
    return SelectAgentModelUseCase(
        run_store=_FakeRunStore(run),
        agent_config=agent_config or _FakeAgentConfig(),
        llm_provider_catalog=_FakeCatalogPort(),
        runtime_events=events or _FakeRuntimeEventStore(),
        skill_runner=_FakeSkillRunner(),
    )


class _FakeRunStore:
    def __init__(self, run: Run | None) -> None:
        self.run = run

    def get_run(self, run_id: str) -> Run | None:
        _ = run_id
        return self.run


class _FakeAgentConfig:
    def __init__(self) -> None:
        self.selections: list[tuple[str, str, Path | None]] = []

    def set_model(
        self,
        *,
        provider: str,
        model: str,
        config_path: Path | None = None,
    ) -> None:
        self.selections.append((provider, model, config_path))


class _FakeRuntimeEventStore:
    def __init__(self) -> None:
        self.events: list[RuntimeEventDraft] = []

    def append_event(self, event: RuntimeEventDraft) -> str:
        self.events.append(event)
        return "event-1"

    def list_events(
        self,
        run_id: str,
        *,
        after_sequence: int | None = None,
        limit: int | None = None,
    ) -> list[RuntimeEvent]:
        _ = run_id, after_sequence, limit
        return []

    def get_last_event(self, run_id: str) -> RuntimeEvent | None:
        _ = run_id
        return None


class _FakeCatalogPort:
    def get_catalog(self) -> LLMProviderCatalog:
        provider = OpenAILLMProviderDefinition(
            name="fake",
            timeout_seconds=30,
            models=(
                LLMModelDefinition(model="model1", context_window_tokens=100_000),
                LLMModelDefinition(model="model2", context_window_tokens=100_000),
            ),
            enabled=True,
            base_url="http://localhost/v1",
            temperature=0,
            top_p=1,
            max_output_tokens=4096,
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
