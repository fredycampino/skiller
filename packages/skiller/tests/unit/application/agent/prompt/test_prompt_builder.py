import pytest

from skiller.application.agent.prompt.prompt_builder import AgentPromptBuilder
from skiller.domain.agent.agent_context_model import AgentContextEntry, AgentContextEntryType
from skiller.domain.agent.llm_model import (
    LLMMessage,
    LLMToolCall,
    LLMToolCallFunction,
)
from skiller.domain.tool.tool_contract import ToolConfig

pytestmark = pytest.mark.unit


def _entry(
    *,
    sequence: int,
    entry_type: AgentContextEntryType,
    payload: dict[str, object],
) -> AgentContextEntry:
    return AgentContextEntry(
        id=f"entry-{sequence}",
        run_id="run-1",
        context_id="thread-1",
        sequence=sequence,
        entry_type=entry_type,
        payload=payload,
        source_step_id="support_agent",
        idempotency_key=f"entry:{sequence}",
        created_at="2026-04-22T00:00:00Z",
    )


def test_agent_prompt_builder_builds_messages() -> None:
    builder = AgentPromptBuilder()
    entries = [
        _entry(
            sequence=1,
            entry_type=AgentContextEntryType.USER_MESSAGE,
            payload={"type": "user_message", "text": "Hello"},
        ),
        _entry(
            sequence=2,
            entry_type=AgentContextEntryType.ASSISTANT_MESSAGE,
            payload={"type": "assistant_message", "turn_id": "turn-1", "text": "Hi"},
        ),
        _entry(
            sequence=3,
            entry_type=AgentContextEntryType.TOOL_CALL,
            payload={
                "type": "tool_call",
                "turn_id": "turn-2",
                "tool_call_id": "call-1",
                "tool": "shell",
                "args": {"x": 1},
            },
        ),
        _entry(
            sequence=4,
            entry_type=AgentContextEntryType.TOOL_RESULT,
            payload={
                "type": "tool_result",
                "turn_id": "turn-2",
                "tool_call_id": "call-1",
                "tool": "shell",
                "status": "COMPLETED",
                "data": {"ok": True},
                "text": "",
                "error": None,
            },
        ),
    ]

    request = builder.build_request(system="Be useful.", entries=entries, tools=[])

    assert request.messages == (
        LLMMessage.system("Be useful."),
        LLMMessage.user("Hello"),
        LLMMessage.assistant("Hi"),
        LLMMessage.assistant(
            tool_calls=(
                LLMToolCall(
                    id="call-1",
                    function=LLMToolCallFunction(
                        name="shell",
                        arguments_json='{"x": 1}',
                    ),
                ),
            )
        ),
        LLMMessage.tool('{"ok": true}', tool_call_id="call-1"),
    )


def test_agent_prompt_builder_merges_assistant_content_with_tool_call() -> None:
    builder = AgentPromptBuilder()
    entries = [
        _entry(
            sequence=1,
            entry_type=AgentContextEntryType.USER_MESSAGE,
            payload={"type": "user_message", "text": "Hello"},
        ),
        _entry(
            sequence=2,
            entry_type=AgentContextEntryType.ASSISTANT_MESSAGE,
            payload={
                "type": "assistant_message",
                "turn_id": "turn-1",
                "text": "I should send a notification.",
            },
        ),
        _entry(
            sequence=3,
            entry_type=AgentContextEntryType.TOOL_CALL,
            payload={
                "type": "tool_call",
                "turn_id": "turn-1",
                "tool_call_id": "call-1",
                "tool": "notify",
                "args": {"x": 1},
            },
        ),
        _entry(
            sequence=4,
            entry_type=AgentContextEntryType.TOOL_RESULT,
            payload={
                "type": "tool_result",
                "turn_id": "turn-1",
                "tool_call_id": "call-1",
                "tool": "notify",
                "status": "COMPLETED",
                "data": {"ok": True},
                "text": "sent",
                "error": None,
            },
        ),
    ]

    request = builder.build_request(system="Be useful.", entries=entries, tools=[])

    assert request.messages == (
        LLMMessage.system("Be useful."),
        LLMMessage.user("Hello"),
        LLMMessage.assistant(
            "I should send a notification.",
            tool_calls=(
                LLMToolCall(
                    id="call-1",
                    function=LLMToolCallFunction(
                        name="notify",
                        arguments_json='{"x": 1}',
                    ),
                ),
            ),
        ),
        LLMMessage.tool("sent", tool_call_id="call-1"),
    )


def test_agent_prompt_builder_preserves_multiple_tool_calls_in_one_turn() -> None:
    builder = AgentPromptBuilder()
    entries = [
        _entry(
            sequence=1,
            entry_type=AgentContextEntryType.USER_MESSAGE,
            payload={"type": "user_message", "text": "Hello"},
        ),
        _entry(
            sequence=2,
            entry_type=AgentContextEntryType.TOOL_CALL,
            payload={
                "type": "tool_call",
                "turn_id": "turn-1",
                "tool_call_id": "call-1",
                "tool": "notify",
                "args": {"message": "hello"},
            },
        ),
        _entry(
            sequence=3,
            entry_type=AgentContextEntryType.TOOL_CALL,
            payload={
                "type": "tool_call",
                "turn_id": "turn-1",
                "tool_call_id": "call-2",
                "tool": "shell",
                "args": {"command": "pwd"},
            },
        ),
        _entry(
            sequence=4,
            entry_type=AgentContextEntryType.TOOL_RESULT,
            payload={
                "type": "tool_result",
                "turn_id": "turn-1",
                "tool_call_id": "call-1",
                "tool": "notify",
                "status": "COMPLETED",
                "data": {"message": "sent"},
                "text": "sent",
                "error": None,
            },
        ),
        _entry(
            sequence=5,
            entry_type=AgentContextEntryType.TOOL_RESULT,
            payload={
                "type": "tool_result",
                "turn_id": "turn-1",
                "tool_call_id": "call-2",
                "tool": "shell",
                "status": "COMPLETED",
                "data": {"ok": True},
                "text": "ok",
                "error": None,
            },
        ),
    ]

    request = builder.build_request(system="Be useful.", entries=entries, tools=[])

    assert request.messages == (
        LLMMessage.system("Be useful."),
        LLMMessage.user("Hello"),
        LLMMessage.assistant(
            tool_calls=(
                LLMToolCall(
                    id="call-1",
                    function=LLMToolCallFunction(
                        name="notify",
                        arguments_json='{"message": "hello"}',
                    ),
                ),
                LLMToolCall(
                    id="call-2",
                    function=LLMToolCallFunction(
                        name="shell",
                        arguments_json='{"command": "pwd"}',
                    ),
                ),
            )
        ),
        LLMMessage.tool("sent", tool_call_id="call-1"),
        LLMMessage.tool("ok", tool_call_id="call-2"),
    )


def test_agent_prompt_builder_returns_single_system_message() -> None:
    builder = AgentPromptBuilder()

    request = builder.build_request(
        system="Be useful.",
        entries=[],
        tools=[],
    )

    assert request.messages == (
        LLMMessage.system("Be useful."),
    )


def test_agent_prompt_builder_adds_tools_to_request() -> None:
    builder = AgentPromptBuilder()
    tool = ToolConfig(
        name="shell",
        description="Run shell command",
        parameters_schema={"type": "object"},
    )

    request = builder.build_request(
        system="Be useful.",
        entries=[],
        tools=[tool],
    )

    assert request.tools == (tool,)
