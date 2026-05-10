from __future__ import annotations

import pytest
from stui.adapter.run_event_mapper import RunEventMapper

pytestmark = pytest.mark.unit


def test_run_event_mapper_extracts_input_received_text_from_nested_payload() -> None:
    mapper = RunEventMapper()

    events = mapper.logs_to_events(
        run_id="run-1",
        events_payload=[
            {
                "id": "evt-1",
                "type": "INPUT_RECEIVED",
                "payload": {
                    "step": "ask_user",
                    "payload": {"text": "database timeout"},
                },
            }
        ],
        seen_event_ids=set(),
    )

    assert len(events) == 1
    assert events[0].event_type == "INPUT_RECEIVED"
    assert events[0].user_input_text == "database timeout"
