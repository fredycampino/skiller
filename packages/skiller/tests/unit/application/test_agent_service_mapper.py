import pytest

from skiller.application.agents.mapper import AgentServiceMapper
from skiller.application.use_cases.agent.get_agent_stats import (
    GetAgentStatsResult,
    GetAgentStatsStatus,
)
from skiller.application.use_cases.agent.interrupt_agent import (
    InterruptAgentResult,
    InterruptAgentStatus,
)
from skiller.domain.agent.agent_stats_model import (
    AgentContextStats,
    AgentContextWindowStats,
    AgentStats,
)
from skiller.domain.run.steering_model import SteeringAgentInterrupt

pytestmark = pytest.mark.unit


def test_mapper_serializes_interrupt_result() -> None:
    mapper = AgentServiceMapper()
    result = InterruptAgentResult(
        status=InterruptAgentStatus.ENQUEUED,
        run_id="run-1",
        item=SteeringAgentInterrupt(),
    )

    assert mapper.to_interrupt_input(" run-1 ") == "run-1"
    assert mapper.to_interrupt_dict(result) == {
        "run_id": "run-1",
        "status": "ENQUEUED",
        "enqueued": True,
        "item": {"type": "agent_interrupt"},
    }


def test_mapper_serializes_agent_stats_result() -> None:
    mapper = AgentServiceMapper()
    stats = AgentStats(
        run_id="run-1",
        agent_id="support",
        context_id="ctx-1",
        context=AgentContextStats(
            entries=3,
            estimated_tokens=125,
            window=AgentContextWindowStats(
                start_sequence=2,
                end_sequence=3,
                current_tokens=100,
                limit_tokens=80000,
                capacity_tokens=100000,
            ),
        ),
    )
    result = GetAgentStatsResult(
        status=GetAgentStatsStatus.OK,
        run_id="run-1",
        agent_id="support",
        stats=stats,
    )

    assert mapper.to_stats_input(" run-1 ", " support ") == ("run-1", "support")
    assert mapper.to_stats_dict(result) == {
        "run_id": "run-1",
        "agent_id": "support",
        "status": "OK",
        "ok": True,
        "context_id": "ctx-1",
        "context": {
            "entries": 3,
            "estimated_tokens": 125,
            "window": {
                "start_sequence": 2,
                "end_sequence": 3,
                "current_tokens": 100,
                "limit_tokens": 80000,
                "capacity_tokens": 100000,
            },
        },
    }
