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
from skiller.application.use_cases.agent.list_agent_context import (
    AgentContextEntryItem,
    AgentContextWindow,
    ListAgentContextResult,
    ListAgentContextStatus,
)
from skiller.application.use_cases.agent.list_agent_models import (
    AgentModelItem,
    AgentModelsProviderItem,
    ListAgentModelsResult,
    ListAgentModelsStatus,
)
from skiller.application.use_cases.agent.list_llm_providers import (
    ListLLMProvidersResult,
    ListLLMProvidersStatus,
    LLMProviderItem,
    LLMProviderModelItem,
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
from skiller.domain.agent.llm.provider_catalog import (
    LLMAdapterType,
    LLMProviderCatalogSource,
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


def test_mapper_serializes_llm_providers_result_without_secrets() -> None:
    mapper = AgentServiceMapper()
    result = ListLLMProvidersResult(
        status=ListLLMProvidersStatus.OK,
        providers=(
            LLMProviderItem(
                name="codex",
                source=LLMProviderCatalogSource.USER,
                adapter=LLMAdapterType.CODEX,
                enabled=True,
                base_url=None,
                timeout_seconds=60.0,
                credentials_file="~/.codex/credentials.json",
                profile=None,
                api_key_file=None,
                models=(
                    LLMProviderModelItem(name="gpt-5.5", context_window_tokens=400_000),
                ),
            ),
        ),
    )

    assert mapper.to_llm_providers_dict(result) == {
        "status": "OK",
        "ok": True,
        "providers": [
            {
                "name": "codex",
                "source": "user",
                "adapter": "codex",
                "enabled": True,
                "base_url": None,
                "timeout_seconds": 60.0,
                "credentials_file": "~/.codex/credentials.json",
                "profile": None,
                "api_key_file": None,
                "models": [
                    {"name": "gpt-5.5", "context_window_tokens": 400_000},
                ],
            },
        ],
    }


def test_mapper_serializes_llm_providers_empty_result() -> None:
    mapper = AgentServiceMapper()
    result = ListLLMProvidersResult(status=ListLLMProvidersStatus.OK)

    assert mapper.to_llm_providers_dict(result) == {
        "status": "OK",
        "ok": True,
        "providers": [],
    }


def test_mapper_serializes_llm_providers_error_result() -> None:
    mapper = AgentServiceMapper()
    result = ListLLMProvidersResult(
        status=ListLLMProvidersStatus.ERROR,
        error="catalog unreadable",
    )

    assert mapper.to_llm_providers_dict(result) == {
        "status": "ERROR",
        "ok": False,
        "error": "catalog unreadable",
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


def test_mapper_serializes_agent_context_result_without_payload() -> None:
    mapper = AgentServiceMapper()
    result = ListAgentContextResult(
        status=ListAgentContextStatus.OK,
        run_id="run-1",
        agent_id="support",
        context_id="ctx-1",
        window=AgentContextWindow(
            mode="compact",
            entries=1,
            start_sequence=3,
            end_sequence=3,
            limit_tokens=80000,
            estimated_tokens=50,
            payload_bytes=128,
            keep_last=10,
        ),
        entries=(
            AgentContextEntryItem(
                sequence=3,
                role="assistant",
                type="final",
                delta_tokens=50,
                delta_compact_tokens=12,
                payload_bytes=128,
                usage=True,
                prunable=False,
                compaction_id=0,
            ),
        ),
    )

    assert mapper.to_context_input(" run-1 ", " support ") == ("run-1", "support")
    assert mapper.to_context_dict(result) == {
        "run_id": "run-1",
        "agent_id": "support",
        "status": "OK",
        "ok": True,
        "context_id": "ctx-1",
        "request_context": {
            "mode": "compact",
            "entries": 1,
            "start_sequence": 3,
            "end_sequence": 3,
            "limit_tokens": 80000,
            "estimated_tokens": 50,
            "payload_bytes": 128,
            "keep_last": 10,
        },
        "entries": [
            {
                "sequence": 3,
                "role": "assistant",
                "type": "final",
                "delta_tokens": 50,
                "delta_compact_tokens": 12,
                "payload_bytes": 128,
                "usage": True,
                "prunable": False,
                "compaction_id": 0,
            },
        ],
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
