import pytest

from skiller.application.agent.context.agent_context_marker_calculator import (
    AgentContextMarkerCalculator,
)
from skiller.domain.agent.context.model import (
    AgentAssistantMessagePayload,
    AgentAssistantMessageType,
    AgentContextPayload,
    AgentContextState,
    AgentContextUsageMarker,
)
from skiller.domain.agent.llm.model import LLMUsage
from skiller.domain.agent.run.identity import AgentContext

pytestmark = pytest.mark.unit

CONTEXT = AgentContext(
    run_id="run-1",
    agent_id="agent-1",
    context_id="ctx-1",
)
PAYLOAD = AgentAssistantMessagePayload(
    turn_id="turn-2",
    message_type=AgentAssistantMessageType.FINAL,
    text="Done.",
)


def test_marker_calculator_uses_prompt_delta_for_same_compaction() -> None:
    store = _FakeAgentContextStore(
        marker=AgentContextUsageMarker(
            sequence=10,
            prompt_tokens=500,
            delta_tokens=200,
            compaction_id=3,
        ),
        estimated_delta_tokens=99,
    )
    calculator = _calculator(store=store, compaction_id=3)

    marker = calculator.calculate(
        context=CONTEXT,
        usage=_usage(prompt_tokens=620),
        payload=PAYLOAD,
    )

    assert marker.delta_tokens == 120
    assert marker.compaction_id == 3
    assert store.estimate_calls == []


@pytest.mark.parametrize("prompt_tokens", [300, 620])
def test_marker_calculator_estimates_when_compaction_changed(
    prompt_tokens: int,
) -> None:
    store = _FakeAgentContextStore(
        marker=AgentContextUsageMarker(
            sequence=10,
            prompt_tokens=500,
            delta_tokens=200,
            compaction_id=2,
        ),
        estimated_delta_tokens=33,
    )
    calculator = _calculator(store=store, compaction_id=3)

    marker = calculator.calculate(
        context=CONTEXT,
        usage=_usage(prompt_tokens=prompt_tokens),
        payload=PAYLOAD,
    )

    assert marker.delta_tokens == 33
    assert marker.compaction_id == 3
    assert store.estimate_calls == [
        {
            "context_id": "ctx-1",
            "start_sequence": 1,
            "last_marker_sequence": 10,
            "payload": PAYLOAD,
        }
    ]


def test_marker_calculator_estimates_first_marker() -> None:
    store = _FakeAgentContextStore(marker=None, estimated_delta_tokens=40)
    calculator = _calculator(store=store, compaction_id=0)

    marker = calculator.calculate(
        context=CONTEXT,
        usage=_usage(prompt_tokens=100),
        payload=PAYLOAD,
    )

    assert marker.delta_tokens == 40
    assert marker.compaction_id == 0
    assert store.estimate_calls[0]["last_marker_sequence"] == 0


def test_marker_calculator_estimates_without_prompt_tokens() -> None:
    store = _FakeAgentContextStore(marker=None, estimated_delta_tokens=37)
    calculator = _calculator(store=store, compaction_id=0)

    marker = calculator.calculate(
        context=CONTEXT,
        usage=LLMUsage(
            estimated_system_tokens=None,
            cache_read_tokens=None,
            cache_write_tokens=None,
            provider=None,
            model=None,
            prompt_tokens=None,
            output_tokens=5,
            total_tokens=None,
        ),
        payload=PAYLOAD,
    )

    assert marker.delta_tokens == 37
    assert marker.compaction_id is None


def _calculator(
    *,
    store: "_FakeAgentContextStore",
    compaction_id: int,
) -> AgentContextMarkerCalculator:
    return AgentContextMarkerCalculator(
        agent_context_store=store,
        agent_context_state=_FakeAgentContextState(compaction_id=compaction_id),
    )


def _usage(*, prompt_tokens: int) -> LLMUsage:
    return LLMUsage(
        estimated_system_tokens=None,
        cache_read_tokens=None,
        cache_write_tokens=None,
        provider=None,
        model=None,
        prompt_tokens=prompt_tokens,
        output_tokens=5,
        total_tokens=prompt_tokens + 5,
    )


class _FakeAgentContextStore:
    def __init__(
        self,
        *,
        marker: AgentContextUsageMarker | None,
        estimated_delta_tokens: int,
    ) -> None:
        self.marker = marker
        self.estimated_delta_tokens = estimated_delta_tokens
        self.estimate_calls: list[dict[str, object]] = []

    def get_last_usage_marker(
        self,
        *,
        context_id: str,
    ) -> AgentContextUsageMarker | None:
        _ = context_id
        return self.marker

    def estimate_delta_tokens(
        self,
        *,
        context_id: str,
        start_sequence: int,
        last_marker_sequence: int,
        payload: AgentContextPayload,
    ) -> int:
        self.estimate_calls.append(
            {
                "context_id": context_id,
                "start_sequence": start_sequence,
                "last_marker_sequence": last_marker_sequence,
                "payload": payload,
            }
        )
        return self.estimated_delta_tokens


class _FakeAgentContextState:
    def __init__(self, *, compaction_id: int) -> None:
        self.state = AgentContextState(
            context_id="ctx-1",
            start_sequence=1,
            compacted_sequence=None,
            compaction_id=compaction_id,
        )

    def get_state(self, *, context_id: str) -> AgentContextState:
        _ = context_id
        return self.state
