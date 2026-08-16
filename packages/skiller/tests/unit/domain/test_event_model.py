import pytest

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
