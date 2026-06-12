import pytest

from skiller.application.agent.prompt.prompt_builder import AgentPromptBuilder
from skiller.application.tools.shell import ShellProcessTool
from skiller.domain.agent.agent_context_model import AgentContextEntry, AgentContextEntryType
from skiller.domain.agent.agent_llm_provider_model import (
    AgentBedrockLLMModel,
    AgentBedrockProvider,
    AgentCodexLLMModel,
    AgentCodexProvider,
    AgentFakeLLMModel,
    AgentFakeProvider,
    AgentMiniMaxLLMModel,
    AgentMiniMaxProvider,
)
from skiller.domain.agent.llm_model import (
    LLMAssistantMessage,
    LLMSystemMessage,
    LLMToolCall,
    LLMToolCallFunction,
    LLMToolMessage,
    LLMUserMessage,
)
from skiller.domain.agent.llm_request import (
    BedrockLLMRequest,
    CodexLLMRequest,
    LLMRequest,
    MiniMaxLLMRequest,
)

pytestmark = pytest.mark.unit


def _provider() -> AgentFakeProvider:
    return AgentFakeProvider(
        model=AgentFakeLLMModel.MODEL1,
        timeout_seconds=30,
        window_width_tokens=100_000,
    )


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
        usage=None,
        payload=payload,
        source_step_id="support_agent",
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
            payload={
                "type": "assistant_message",
                "turn_id": "turn-1",
                "message_type": "final",
                "text": "Hi",
            },
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

    request = builder.build_request(
        provider=_provider(),
        system="Be useful.",
        entries=entries,
        tools=(),
    )

    assert request.model == "model1"
    assert isinstance(request, LLMRequest)
    assert not isinstance(request, MiniMaxLLMRequest)
    assert request.messages == (
        LLMSystemMessage("Be useful."),
        LLMUserMessage("Hello"),
        LLMAssistantMessage("Hi"),
        LLMAssistantMessage(
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
        LLMToolMessage(
            '{"data": {"ok": true}, "status": "COMPLETED", "tool": "shell"}',
            tool_call_id="call-1",
        ),
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
                "message_type": "tool_calls",
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

    request = builder.build_request(
        provider=_provider(),
        system="Be useful.",
        entries=entries,
        tools=(),
    )

    assert request.messages == (
        LLMSystemMessage("Be useful."),
        LLMUserMessage("Hello"),
        LLMAssistantMessage(
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
        LLMToolMessage(
            '{"data": {"ok": true}, "status": "COMPLETED", "tool": "notify"}',
            tool_call_id="call-1",
        ),
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
                "error": None,
            },
        ),
    ]

    request = builder.build_request(
        provider=_provider(),
        system="Be useful.",
        entries=entries,
        tools=(),
    )

    assert request.messages == (
        LLMSystemMessage("Be useful."),
        LLMUserMessage("Hello"),
        LLMAssistantMessage(
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
        LLMToolMessage(
            '{"data": {"message": "sent"}, "status": "COMPLETED", "tool": "notify"}',
            tool_call_id="call-1",
        ),
        LLMToolMessage(
            '{"data": {"ok": true}, "status": "COMPLETED", "tool": "shell"}',
            tool_call_id="call-2",
        ),
    )


def test_agent_prompt_builder_returns_single_system_message() -> None:
    builder = AgentPromptBuilder()

    request = builder.build_request(
        provider=_provider(),
        system="Be useful.",
        entries=[],
        tools=(),
    )

    assert request.messages == (
        LLMSystemMessage("Be useful."),
    )


def test_agent_prompt_builder_adds_minimax_generation_fields() -> None:
    builder = AgentPromptBuilder()
    provider = AgentMiniMaxProvider(
        model=AgentMiniMaxLLMModel.M2_7,
        api_key="secret",
        timeout_seconds=30,
        window_width_tokens=100_000,
    )

    request = builder.build_request(
        provider=provider,
        system="Be useful.",
        entries=[],
        tools=(),
    )

    assert isinstance(request, MiniMaxLLMRequest)
    assert request.temperature == 1
    assert request.max_tokens == 4096
    assert request.top_p == 1


def test_agent_prompt_builder_returns_codex_request() -> None:
    builder = AgentPromptBuilder()
    provider = AgentCodexProvider(
        model=AgentCodexLLMModel.GPT_5_5,
        credentials_file="/tmp/openai-codex.json",
        timeout_seconds=120,
        window_width_tokens=100_000,
    )

    request = builder.build_request(
        provider=provider,
        system="Be useful.",
        entries=[],
        tools=(),
    )

    assert isinstance(request, CodexLLMRequest)
    assert request.model == AgentCodexLLMModel.GPT_5_5
    assert request.parallel_tool_calls is True
    assert not hasattr(request, "temperature")
    assert not hasattr(request, "max_tokens")
    assert not hasattr(request, "top_p")


def test_agent_prompt_builder_returns_bedrock_request() -> None:
    builder = AgentPromptBuilder()
    provider = AgentBedrockProvider(
        model=AgentBedrockLLMModel.CLAUDE_OPUS_4_6,
        profile="claude-bedrock",
        timeout_seconds=120,
        window_width_tokens=200_000,
    )

    request = builder.build_request(
        provider=provider,
        system="Be useful.",
        entries=[],
        tools=(),
    )

    assert isinstance(request, BedrockLLMRequest)
    assert request.model == AgentBedrockLLMModel.CLAUDE_OPUS_4_6
    assert not hasattr(request, "temperature")
    assert not hasattr(request, "max_tokens")
    assert not hasattr(request, "top_p")


def test_agent_prompt_builder_adds_tools_to_request() -> None:
    builder = AgentPromptBuilder()
    tool = ShellProcessTool()

    request = builder.build_request(
        provider=_provider(),
        system="Be useful.",
        entries=[],
        tools=(tool,),
    )

    assert request.tools == (tool,)
