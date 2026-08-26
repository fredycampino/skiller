import pytest

from skiller.domain.event.event_agent_model import AgentContextCompactedPayload
from skiller.domain.event.event_model import (
    RunModelUpdatedPayload,
    RuntimeEventType,
    runtime_event_payload_from_dict,
    runtime_event_payload_to_dict,
)

pytestmark = pytest.mark.unit


def test_action_done_payload_requires_uid() -> None:
    with pytest.raises(ValueError, match="ACTION_DONE uid must be non-empty string"):
        runtime_event_payload_from_dict(
            event_type=RuntimeEventType.ACTION_DONE,
            value={
                "type": "open_url",
                "status": "done",
            },
        )


def test_legacy_agent_message_context_keeps_metrics_without_model_window() -> None:
    payload = runtime_event_payload_from_dict(
        event_type=RuntimeEventType.AGENT_ASSISTANT_MESSAGE,
        value={
            "step_id": "support_agent",
            "turn_id": "turn-1",
            "agent_sequence": 1,
            "body": {
                "total_tokens": 100,
                "text": "Inspecting.",
                "context": {
                    "effective_window_tokens": 100_000,
                    "max_total_tokens_ratio": 0.8,
                },
            },
        },
    )

    assert payload.body.context is not None
    assert payload.body.context.effective_window_tokens == 100_000
    assert payload.body.context.max_total_tokens_ratio == 0.8
    assert payload.body.context.window_width_tokens is None
    assert payload.body.context.model_context_window_tokens is None


def test_context_compacted_payload_round_trips() -> None:
    payload = AgentContextCompactedPayload(
        context_id="ctx-1",
        compaction_id=2,
        system_tokens=2_000,
        estimated_request_tokens=80_000,
        estimated_request_compacted_tokens=50_000,
        target_tokens=50_000,
        window_tokens=100_000,
    )

    encoded = runtime_event_payload_to_dict(payload)
    decoded = runtime_event_payload_from_dict(
        event_type=RuntimeEventType.AGENT_CONTEXT_COMPACTED,
        value=encoded,
    )

    assert decoded == payload
    assert encoded == {
        "context_id": "ctx-1",
        "compaction_id": 2,
        "system_tokens": 2_000,
        "estimated_request_tokens": 80_000,
        "estimated_request_compacted_tokens": 50_000,
        "target_tokens": 50_000,
        "window_tokens": 100_000,
    }


def test_model_updated_payload_round_trips() -> None:
    payload = runtime_event_payload_from_dict(
        event_type=RuntimeEventType.RUN_MODEL_UPDATED,
        value={"provider": "moonshot", "model": "kimi-k3"},
    )

    assert payload == RunModelUpdatedPayload(provider="moonshot", model="kimi-k3")
    assert runtime_event_payload_to_dict(payload) == {
        "provider": "moonshot",
        "model": "kimi-k3",
    }
