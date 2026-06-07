import pytest

from skiller.domain.event.event_model import (
    RuntimeEventType,
    runtime_event_payload_from_dict,
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
