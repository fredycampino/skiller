import pytest

from skiller.application.use_cases.agent.get_agent_stats import (
    GetAgentStatsStatus,
    GetAgentStatsUseCase,
)
from skiller.domain.agent.config.model import (
    AgentConfig,
    AgentContextCompactionConfig,
    AgentContextConfig,
    AgentEventOutputConfig,
    AgentEventOutputTruncateConfig,
    AgentLoopConfig,
)
from skiller.domain.agent.context.stats_model import (
    AgentContextObservedStats,
    AgentContextObservedWindowStats,
)
from skiller.domain.agent.llm.provider_registry import (
    NULL_MODELS,
    AgentLLMProviderList,
    AgentLLMProviderType,
    AgentNullLLMModel,
    AgentNullProvider,
)
from skiller.domain.run.run_context_model import RunContext
from skiller.domain.run.run_model import Run, RunAgent

pytestmark = pytest.mark.unit


def test_get_agent_stats_uses_attached_agent_context_id() -> None:
    context_stats = _FakeContextStats()
    use_case = GetAgentStatsUseCase(
        run_store=_FakeRunStore(_build_run()),
        run_agent_store=_FakeRunAgentStore(RunAgent("support_agent", "support-thread")),
        context_stats=context_stats,
        agent_config=_FakeAgentConfig(),
        skill_runner=_FakeSkillRunner(),
    )

    result = use_case.execute("run-1", "support_agent")

    assert result.status == GetAgentStatsStatus.OK
    assert result.stats is not None
    assert result.stats.run_id == "run-1"
    assert result.stats.agent_id == "support_agent"
    assert result.stats.context_id == "support-thread"
    assert result.stats.context.window.current_tokens == 100
    assert result.stats.context.window.limit_tokens == 80000
    assert result.stats.context.window.capacity_tokens == 100000
    assert context_stats.context_ids == ["support-thread"]


def test_get_agent_stats_caps_capacity_by_model_context_window() -> None:
    result = GetAgentStatsUseCase(
        run_store=_FakeRunStore(_build_run()),
        run_agent_store=_FakeRunAgentStore(RunAgent("support_agent", "support-thread")),
        context_stats=_FakeContextStats(),
        agent_config=_FakeAgentConfig(_agent_config(window_width_tokens=120000)),
        skill_runner=_FakeSkillRunner(),
    ).execute("run-1", "support_agent")

    assert result.status == GetAgentStatsStatus.OK
    assert result.stats is not None
    assert result.stats.context.window.capacity_tokens == 100000
    assert result.stats.context.window.limit_tokens == 80000


def test_get_agent_stats_uses_configured_capacity_when_smaller_than_model() -> None:
    result = GetAgentStatsUseCase(
        run_store=_FakeRunStore(_build_run()),
        run_agent_store=_FakeRunAgentStore(RunAgent("support_agent", "support-thread")),
        context_stats=_FakeContextStats(),
        agent_config=_FakeAgentConfig(_agent_config(window_width_tokens=60000)),
        skill_runner=_FakeSkillRunner(),
    ).execute("run-1", "support_agent")

    assert result.status == GetAgentStatsStatus.OK
    assert result.stats is not None
    assert result.stats.context.window.capacity_tokens == 60000
    assert result.stats.context.window.limit_tokens == 48000


def test_get_agent_stats_returns_not_found_statuses() -> None:
    missing_run = GetAgentStatsUseCase(
        run_store=_FakeRunStore(None),
        run_agent_store=_FakeRunAgentStore(None),
        context_stats=_FakeContextStats(),
        agent_config=_FakeAgentConfig(),
        skill_runner=_FakeSkillRunner(),
    ).execute("missing-run", "support_agent")
    missing_agent = GetAgentStatsUseCase(
        run_store=_FakeRunStore(_build_run()),
        run_agent_store=_FakeRunAgentStore(None),
        context_stats=_FakeContextStats(),
        agent_config=_FakeAgentConfig(),
        skill_runner=_FakeSkillRunner(),
    ).execute("run-1", "support_agent")

    assert missing_run.status == GetAgentStatsStatus.RUN_NOT_FOUND
    assert missing_run.error == "Run 'missing-run' not found"
    assert missing_agent.status == GetAgentStatsStatus.AGENT_NOT_FOUND
    assert missing_agent.error == "Agent 'support_agent' not found in run 'run-1'"


def test_get_agent_stats_returns_context_not_ready() -> None:
    result = GetAgentStatsUseCase(
        run_store=_FakeRunStore(_build_run()),
        run_agent_store=_FakeRunAgentStore(RunAgent("support_agent", None)),
        context_stats=_FakeContextStats(),
        agent_config=_FakeAgentConfig(),
        skill_runner=_FakeSkillRunner(),
    ).execute("run-1", "support_agent")

    assert result.status == GetAgentStatsStatus.AGENT_CONTEXT_NOT_READY
    assert result.error == "Agent 'support_agent' has no attached context in run 'run-1'"


def test_get_agent_stats_rejects_invalid_programmer_input() -> None:
    use_case = GetAgentStatsUseCase(
        run_store=_FakeRunStore(_build_run()),
        run_agent_store=_FakeRunAgentStore(None),
        context_stats=_FakeContextStats(),
        agent_config=_FakeAgentConfig(),
        skill_runner=_FakeSkillRunner(),
    )

    with pytest.raises(RuntimeError, match="requires run_id and agent_id"):
        use_case.execute("", "support_agent")

    with pytest.raises(RuntimeError, match="requires run_id and agent_id"):
        use_case.execute("run-1", "")


class _FakeRunStore:
    def __init__(self, run: Run | None) -> None:
        self.run = run

    def get_run(self, run_id: str) -> Run | None:
        _ = run_id
        return self.run


class _FakeRunAgentStore:
    def __init__(self, agent: RunAgent | None) -> None:
        self.agent = agent

    def get_agent(self, *, run_id: str, agent_id: str) -> RunAgent | None:
        _ = run_id, agent_id
        return self.agent


class _FakeContextStats:
    def __init__(self) -> None:
        self.context_ids: list[str] = []

    def get_stats(self, *, context_id: str) -> AgentContextObservedStats:
        self.context_ids.append(context_id)
        return AgentContextObservedStats(
            entries=3,
            estimated_tokens=125,
            window=AgentContextObservedWindowStats(
                start_sequence=2,
                end_sequence=3,
                current_tokens=100,
            ),
        )


class _FakeAgentConfig:
    def __init__(self, config: AgentConfig | None = None) -> None:
        self.config = config or _agent_config()

    def get_config(self, *, config_path=None) -> AgentConfig:  # noqa: ANN001
        _ = config_path
        return self.config


class _FakeSkillRunner:
    def resolve_file_path(self, source: str, ref: str, file_ref: str):  # noqa: ANN001
        _ = source, ref, file_ref
        raise FileNotFoundError


def _agent_config(*, window_width_tokens: int = 100000) -> AgentConfig:
    provider = AgentNullProvider(
        model=AgentNullLLMModel.NULL1,
        models=NULL_MODELS,
        timeout_seconds=30,
        window_width_tokens=window_width_tokens,
    )
    return AgentConfig(
        llm=AgentLLMProviderList(
            default_provider=AgentLLMProviderType.NULL,
            providers=(provider,),
        ),
        loop=AgentLoopConfig(
            max_turns=2,
            max_tool_calls=3,
        ),
        context=AgentContextConfig(
            compaction=AgentContextCompactionConfig(
                enabled=False,
                max_total_tokens_ratio=0.8,
            ),
        ),
        event_output=AgentEventOutputConfig(
            truncate=AgentEventOutputTruncateConfig(
                enabled=True,
                max_text_chars=100,
                max_json_chars=1000,
                max_array_items=10,
            ),
        ),
    )


def _build_run() -> Run:
    return Run(
        id="run-1",
        source="internal",
        ref="demo",
        snapshot={"start": "support_agent", "steps": [{"agent": "support_agent"}]},
        status="RUNNING",
        current="support_agent",
        context=RunContext(inputs={}, step_executions={}),
        created_at="2026-05-16T00:00:00Z",
        updated_at="2026-05-16T00:00:00Z",
    )
