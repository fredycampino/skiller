import pytest

from skiller.application.agent.prompt.prompt_builder import AgentPromptBuilder
from skiller.application.tools.shell import ShellProcessTool
from skiller.domain.agent.context.model import AgentContextEntry, AgentContextEntryType
from skiller.domain.agent.llm.model import (
    LLMAssistantMessage,
    LLMSystemMessage,
    LLMToolCall,
    LLMToolCallFunction,
    LLMToolChoiceMode,
    LLMToolMessage,
    LLMUserMessage,
)
from skiller.domain.agent.llm.provider_bedrock import BedrockLLMRequest
from skiller.domain.agent.llm.provider_catalog import (
    BedrockLLMProviderDefinition,
    CodexLLMProviderDefinition,
    LLMModelDefinition,
    OpenAILLMProviderDefinition,
)
from skiller.domain.agent.llm.provider_codex import CodexLLMRequest
from skiller.domain.agent.llm.request import LLMRequest, OpenAILLMRequest

pytestmark = pytest.mark.unit


def _model(value: str = "model1", context_window_tokens: int = 100_000) -> LLMModelDefinition:
    return LLMModelDefinition(model=value, context_window_tokens=context_window_tokens)


def _provider(
    *,
    name: str = "fake",
    model: LLMModelDefinition | None = None,
    temperature: float = 0,
) -> OpenAILLMProviderDefinition:
    selected_model = model or _model()
    return OpenAILLMProviderDefinition(
        name=name,
        timeout_seconds=30,
        models=(selected_model,),
        enabled=True,
        base_url="http://localhost/v1",
        temperature=temperature,
        top_p=1,
        max_output_tokens=4096,
        parallel_tool_calls=True,
        tool_choice=LLMToolChoiceMode.AUTO,
        api_key_source=None,
        options={},
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
        model=_model(),
        system="Be useful.",
        entries=entries,
        tools=(),
        context_id="context-1",
        log_request_file=None,
        log_override_file=True,
    )

    assert request.model == _model()
    assert isinstance(request, LLMRequest)
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
        model=_model(),
        system="Be useful.",
        entries=entries,
        tools=(),
        context_id="context-1",
        log_request_file=None,
        log_override_file=True,
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
        model=_model(),
        system="Be useful.",
        entries=entries,
        tools=(),
        context_id="context-1",
        log_request_file=None,
        log_override_file=True,
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
        model=_model(),
        system="Be useful.",
        entries=[],
        tools=(),
        context_id="context-1",
        log_request_file=None,
        log_override_file=True,
    )

    assert request.messages == (LLMSystemMessage("Be useful."),)


def test_agent_prompt_builder_adds_minimax_generation_fields() -> None:
    builder = AgentPromptBuilder()
    provider = _provider(
        name="minimax",
        model=_model("MiniMax-M2.7", 204_800),
        temperature=1,
    )

    request = builder.build_request(
        provider=provider,
        model=provider.models[0],
        system="Be useful.",
        entries=[],
        tools=(),
        context_id="context-1",
        log_request_file=None,
        log_override_file=True,
    )

    assert isinstance(request, OpenAILLMRequest)
    assert request.temperature == 1
    assert request.max_tokens == 4096
    assert request.top_p == 1


def test_agent_prompt_builder_adds_lmstudio_generation_fields() -> None:
    builder = AgentPromptBuilder()
    provider = _provider(
        name="lmstudio",
        model=_model("google/gemma-4-12b-qat", 131_072),
        temperature=0.2,
    )

    request = builder.build_request(
        provider=provider,
        model=provider.models[0],
        system="Be useful.",
        entries=[],
        tools=(),
        context_id="context-1",
        log_request_file=None,
        log_override_file=True,
    )

    assert isinstance(request, OpenAILLMRequest)
    assert request.temperature == 0.2
    assert request.max_tokens == 4096
    assert request.top_p == 1


def test_agent_prompt_builder_returns_codex_request() -> None:
    builder = AgentPromptBuilder()
    model = _model("gpt-5.5", 1_050_000)
    provider = CodexLLMProviderDefinition(
        name="codex",
        models=(model,),
        enabled=True,
        credentials_file="/tmp/openai-codex.json",
        timeout_seconds=120,
        parallel_tool_calls=True,
    )

    request = builder.build_request(
        provider=provider,
        model=provider.models[0],
        system="Be useful.",
        entries=[],
        tools=(),
        context_id="context-1",
        log_request_file=None,
        log_override_file=True,
    )

    assert isinstance(request, CodexLLMRequest)
    assert request.model == model
    assert request.parallel_tool_calls is True
    assert request.session_id == "context-1"
    assert not hasattr(request, "temperature")
    assert not hasattr(request, "max_tokens")
    assert not hasattr(request, "top_p")


def test_agent_prompt_builder_returns_bedrock_request() -> None:
    builder = AgentPromptBuilder()
    model = _model("us.anthropic.claude-opus-4-6-v1", 200_000)
    provider = BedrockLLMProviderDefinition(
        name="bedrock",
        models=(model,),
        enabled=True,
        profile="claude-bedrock",
        timeout_seconds=120,
        max_output_tokens=4096,
    )

    request = builder.build_request(
        provider=provider,
        model=provider.models[0],
        system="Be useful.",
        entries=[],
        tools=(),
        context_id="context-1",
        log_request_file=None,
        log_override_file=True,
    )

    assert isinstance(request, BedrockLLMRequest)
    assert request.model == model
    assert request.max_tokens == 4096
    assert not hasattr(request, "top_p")


def test_agent_prompt_builder_adds_tools_to_request() -> None:
    builder = AgentPromptBuilder()
    tool = ShellProcessTool()

    request = builder.build_request(
        provider=_provider(),
        model=_model(),
        system="Be useful.",
        entries=[],
        tools=(tool,),
        context_id="context-1",
        log_request_file=None,
        log_override_file=True,
    )

    assert request.tools == (tool,)
