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
from skiller.application.use_cases.agent.list_agent_models import (
    AgentModelItem,
    AgentModelsProviderItem,
    ListAgentModelsResult,
    ListAgentModelsStatus,
)
from skiller.application.use_cases.agent.select_agent_model import (
    SelectAgentModelResult,
    SelectAgentModelStatus,
)
from skiller.domain.agent.config.port import AgentConfigProviderSource
from skiller.domain.agent.context.stats_model import (
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


def test_mapper_serializes_agent_models_result_without_secrets() -> None:
    mapper = AgentServiceMapper()
    result = ListAgentModelsResult(
        status=ListAgentModelsStatus.OK,
        run_id="run-1",
        providers=(
            AgentModelsProviderItem(
                name="codex",
                source=AgentConfigProviderSource.GLOBAL,
                models=(
                    AgentModelItem(name="gpt-5.5", active=True),
                    AgentModelItem(name="gpt-5.4", active=False),
                ),
            ),
        ),
    )

    assert mapper.to_models_input(" run-1 ") == "run-1"
    assert mapper.to_models_dict(result) == {
        "run_id": "run-1",
        "status": "OK",
        "ok": True,
        "providers": [
            {
                "name": "codex",
                "source": "global",
                "models": [
                    {"name": "gpt-5.5", "active": True},
                    {"name": "gpt-5.4", "active": False},
                ],
            },
        ],
    }


def test_mapper_serializes_select_agent_model_result() -> None:
    mapper = AgentServiceMapper()
    result = SelectAgentModelResult(
        status=SelectAgentModelStatus.OK,
        run_id="run-1",
        provider="codex",
        model="gpt-5.4",
    )

    assert mapper.to_select_model_input(" run-1 ", " codex ", " gpt-5.4 ") == (
        "run-1",
        "codex",
        "gpt-5.4",
    )
    assert mapper.to_select_model_dict(result) == {
        "run_id": "run-1",
        "provider": "codex",
        "model": "gpt-5.4",
        "status": "OK",
        "ok": True,
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
