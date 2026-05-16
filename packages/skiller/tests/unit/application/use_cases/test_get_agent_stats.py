import pytest

from skiller.application.use_cases.agent.get_agent_stats import (
    GetAgentStatsStatus,
    GetAgentStatsUseCase,
)
from skiller.domain.agent.agent_run_scope import AgentRunScope
from skiller.domain.agent.agent_stats_model import (
    AgentContextEntryStats,
    AgentContextStats,
    AgentContextUsageStats,
)
from skiller.domain.run.run_context_model import RunContext
from skiller.domain.run.run_model import Run, RunAgent

pytestmark = pytest.mark.unit


def test_get_agent_stats_uses_attached_agent_context_id() -> None:
    context_stats = _FakeContextStats()
    use_case = GetAgentStatsUseCase(
        store=_FakeStore(_build_run(), RunAgent("support_agent", "support-thread")),
        context_stats=context_stats,
    )

    result = use_case.execute("run-1", "support_agent")

    assert result.status == GetAgentStatsStatus.OK
    assert result.stats is not None
    assert result.stats.run_id == "run-1"
    assert result.stats.agent_id == "support_agent"
    assert result.stats.context_id == "support-thread"
    assert context_stats.scopes == [
        {
            "run_id": "run-1",
            "agent_id": "support_agent",
            "context_id": "support-thread",
        }
    ]

def test_get_agent_stats_returns_not_found_statuses() -> None:
    missing_run = GetAgentStatsUseCase(
        store=_FakeStore(None, None),
        context_stats=_FakeContextStats(),
    ).execute("missing-run", "support_agent")
    missing_agent = GetAgentStatsUseCase(
        store=_FakeStore(_build_run(), None),
        context_stats=_FakeContextStats(),
    ).execute("run-1", "support_agent")

    assert missing_run.status == GetAgentStatsStatus.RUN_NOT_FOUND
    assert missing_run.error == "Run 'missing-run' not found"
    assert missing_agent.status == GetAgentStatsStatus.AGENT_NOT_FOUND
    assert missing_agent.error == "Agent 'support_agent' not found in run 'run-1'"


def test_get_agent_stats_returns_context_not_ready() -> None:
    result = GetAgentStatsUseCase(
        store=_FakeStore(_build_run(), RunAgent("support_agent", None)),
        context_stats=_FakeContextStats(),
    ).execute("run-1", "support_agent")

    assert result.status == GetAgentStatsStatus.AGENT_CONTEXT_NOT_READY
    assert result.error == "Agent 'support_agent' has no attached context in run 'run-1'"


def test_get_agent_stats_rejects_invalid_programmer_input() -> None:
    use_case = GetAgentStatsUseCase(
        store=_FakeStore(_build_run(), None),
        context_stats=_FakeContextStats(),
    )

    with pytest.raises(RuntimeError, match="requires run_id and agent_id"):
        use_case.execute("", "support_agent")

    with pytest.raises(RuntimeError, match="requires run_id and agent_id"):
        use_case.execute("run-1", "")


class _FakeStore:
    def __init__(self, run: Run | None, agent: RunAgent | None) -> None:
        self.run = run
        self.agent = agent

    def get_run(self, run_id: str) -> Run | None:
        _ = run_id
        return self.run

    def get_agent(self, *, run_id: str, agent_id: str) -> RunAgent | None:
        _ = run_id, agent_id
        return self.agent


class _FakeContextStats:
    def __init__(self) -> None:
        self.scopes: list[dict[str, str]] = []

    def get_stats(self, *, scope: AgentRunScope) -> AgentContextStats:
        self.scopes.append(
            {
                "run_id": scope.run_id,
                "agent_id": scope.agent_id,
                "context_id": scope.context_id,
            }
        )
        return AgentContextStats(
            entries=AgentContextEntryStats(
                total=3,
                user_messages=1,
                assistant_messages=1,
                tool_calls=1,
                tool_results=0,
            ),
            usage=AgentContextUsageStats(
                entries=1,
                total_prompt_tokens=100,
                total_response_tokens=25,
                total_tokens=125,
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
