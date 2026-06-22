import pytest

from skiller.application.agent.config.output_truncator import OutputTruncator
from skiller.application.agent.event.agent_event_truncator import (
    AgentEventOutputPolicy,
    AgentEventTruncator,
)
from skiller.domain.event.event_agent_model import (
    AgentMessageEventBody,
    AgentToolCallEventBody,
    AgentToolResultEventBody,
)

pytestmark = pytest.mark.unit


def test_agent_event_truncator_truncates_assistant_message_text() -> None:
    truncator = AgentEventTruncator(
        AgentEventOutputPolicy(
            truncate_enabled=True,
            max_text_chars=10,
            max_json_chars=1000,
            max_array_items=10,
        ),
        OutputTruncator(),
    )

    payload = truncator.truncate_assistant_message(
        AgentMessageEventBody(
            total_tokens=125,
            text="abcdefghijklmnopqrstuvwxyz",
        )
    )

    assert payload.text == "abcdefghij..."


def test_agent_event_truncator_truncates_tool_call_args() -> None:
    truncator = AgentEventTruncator(
        AgentEventOutputPolicy(
            truncate_enabled=True,
            max_text_chars=8,
            max_json_chars=70,
            max_array_items=2,
        ),
        OutputTruncator(),
    )

    payload = truncator.truncate_tool_call(
        AgentToolCallEventBody(
            turn_id="turn-1",
            parent_sequence=3,
            tool_call_id="call-1",
            tool="shell",
            args={
                "command": "abcdefghijklmnopqrstuvwxyz",
                "logs": ["line1", "line2", "line3"],
            },
        )
    )

    assert payload.args["command"] == "abcdefgh..."
    assert payload.args["logs"] == ["line1", "line2"]


def test_agent_event_truncator_caps_large_tool_call_json_payload() -> None:
    truncator = AgentEventTruncator(
        AgentEventOutputPolicy(
            truncate_enabled=True,
            max_text_chars=100,
            max_json_chars=30,
            max_array_items=20,
        ),
        OutputTruncator(),
    )

    payload = truncator.truncate_tool_call(
        AgentToolCallEventBody(
            turn_id="turn-1",
            parent_sequence=None,
            tool_call_id="call-1",
            tool="notify",
            args={"message": "x" * 100},
        )
    )

    assert payload.args["truncated"] is True
    assert payload.args["preview"].endswith("...")


def test_agent_event_truncator_truncates_tool_result_fields() -> None:
    truncator = AgentEventTruncator(
        AgentEventOutputPolicy(
            truncate_enabled=True,
            max_text_chars=8,
            max_json_chars=200,
            max_array_items=2,
        ),
        OutputTruncator(),
    )

    payload = truncator.truncate_tool_result(
        payload=AgentToolResultEventBody(
            turn_id="turn-1",
            parent_sequence=3,
            tool_call_id="call-1",
            tool="shell",
            status="COMPLETED",
            data={
                "stdout": "abcdefghijklmnopqrstuvwxyz",
                "items": ["one", "two", "three"],
            },
            text="abcdefghijklmnopqrstuvwxyz",
            error="mnopqrstuvwxyz",
        )
    )

    assert payload.data["stdout"] == "abcdefgh..."
    assert payload.data["items"] == ["one", "two"]
    assert payload.text == "abcdefgh..."
    assert payload.error == "mnopqrst..."
