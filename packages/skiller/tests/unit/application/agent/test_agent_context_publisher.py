import pytest

from skiller.application.agent.context.agent_context_publisher import (
    AgentContextPublisher,
)
from skiller.application.agent.mapper.feedback import AgentRunnerFeedback
from skiller.domain.agent.agent_context_model import (
    AgentAssistantMessagePayload,
    AgentContextEntry,
    AgentContextEntryType,
    AgentToolCallPayload,
    AgentToolResultPayload,
    AgentUserMessagePayload,
)
from skiller.domain.agent.agent_context_store_port import AgentContextStorePort
from skiller.domain.agent.agent_loop_model import AgentLoop
from skiller.domain.agent.agent_run_scope import AgentRunScope
from skiller.domain.agent.llm_model import (
    LLMResponse,
    LLMToolCall,
    LLMToolCallFunction,
)
from skiller.domain.tool.tool_contract import ToolResult, ToolResultStatus
from skiller.domain.tool.tool_execution_model import ToolExecutionRequest

pytestmark = pytest.mark.unit


def test_agent_context_publisher_publishes_tool_entries_with_normalized_data() -> None:
    store = _FakeAgentContextStore()
    publisher = AgentContextPublisher(store, AgentRunnerFeedback())
    request = _tool_request()
    tool_call = LLMToolCall(
        id="call-1",
        function=LLMToolCallFunction(
            name="  ",
            arguments_json='{"command":"pwd"}',
        ),
    )

    tool_call_entry = publisher.publish_tool_call(
        request=request,
        raw_tool_call=tool_call,
        parent_sequence=5,
        parsed_args={"command": "pwd"},
    )
    tool_result_entry = publisher.publish_tool_result(
        request=request,
        tool_call=tool_call,
        parent_sequence=5,
        result=ToolResult(
            name="shell",
            status=ToolResultStatus.COMPLETED,
            data={"stdout": "ok"},
            text="ok",
        ),
    )

    assert tool_call_entry.entry_type == AgentContextEntryType.TOOL_CALL
    assert tool_result_entry.entry_type == AgentContextEntryType.TOOL_RESULT
    assert store.calls == [
        {
            "kind": "tool_call",
            "tool": "unknown",
            "args": {"command": "pwd"},
        },
        {
            "kind": "tool_result",
            "tool": "shell",
        },
    ]


def test_agent_context_publisher_publishes_tool_feedback_messages() -> None:
    store = _FakeAgentContextStore()
    publisher = AgentContextPublisher(store, AgentRunnerFeedback())
    request = _tool_request()

    limit_entry = publisher.publish_tool_limit_feedback(
        request=request,
        tool_call_count=7,
    )
    interrupt_entry = publisher.publish_interrupt_feedback(request=request)
    invalid_entry = publisher.publish_invalid_tool_call(
        request=request,
        tool_call=LLMToolCall(
            id="call-1",
            function=LLMToolCallFunction(
                name="notify",
                arguments_json='{"message"',
            ),
        ),
        error=ValueError("invalid JSON"),
    )

    assert limit_entry.entry_type == AgentContextEntryType.USER_MESSAGE
    assert interrupt_entry.entry_type == AgentContextEntryType.USER_MESSAGE
    assert invalid_entry.entry_type == AgentContextEntryType.USER_MESSAGE
    assert [call["turn_id"] for call in store.calls] == [
        "turn-1:tool-limit",
        "turn-1:interrupt",
        "turn-1:tool-format",
    ]

def _tool_request() -> ToolExecutionRequest:
    return ToolExecutionRequest(
        run_id="run-1",
        step_id="agent-1",
        context_id="ctx-1",
        turn_id="turn-1",
        response=LLMResponse(ok=True),
        allowed_tools=["notify"],
        max_tool_calls=5,
        turn_loop=AgentLoop(max_turns=10),
    )


class _FakeAgentContextStore(AgentContextStorePort):
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def init_db(self) -> None:
        raise NotImplementedError

    def append_user_message(
        self,
        *,
        scope: AgentRunScope,
        turn_id: str,
        text: str,
    ) -> AgentContextEntry:
        self.calls.append({"kind": "user", "turn_id": turn_id, "text": text})
        return AgentContextEntry(
            id="entry-1",
            run_id=scope.run_id,
            context_id=scope.context_id,
            sequence=1,
            entry_type=AgentContextEntryType.USER_MESSAGE,
            payload=AgentUserMessagePayload(text=text),
            source_step_id=scope.agent_id,
            idempotency_key="user:1",
            created_at="2026-05-15T00:00:00Z",
        )

    def append_assistant_message(
        self,
        *,
        scope: AgentRunScope,
        turn_id: str,
        message_type: str,
        text: str,
    ) -> AgentContextEntry:
        self.calls.append(
            {
                "kind": "assistant",
                "turn_id": turn_id,
                "message_type": message_type,
                "text": text,
            }
        )
        return AgentContextEntry(
            id="entry-2",
            run_id=scope.run_id,
            context_id=scope.context_id,
            sequence=2,
            entry_type=AgentContextEntryType.ASSISTANT_MESSAGE,
            payload=AgentAssistantMessagePayload(
                turn_id=turn_id,
                message_type=message_type,
                text=text,
            ),
            source_step_id=scope.agent_id,
            idempotency_key="assistant:1",
            created_at="2026-05-15T00:00:00Z",
        )

    def append_tool_call(
        self,
        *,
        scope: AgentRunScope,
        turn_id: str,
        parent_sequence: int | None,
        tool_call_id: str,
        tool: str,
        args: dict[str, object],
    ) -> AgentContextEntry:
        self.calls.append({"kind": "tool_call", "tool": tool, "args": args})
        return AgentContextEntry(
            id="entry-3",
            run_id=scope.run_id,
            context_id=scope.context_id,
            sequence=3,
            entry_type=AgentContextEntryType.TOOL_CALL,
            payload=AgentToolCallPayload(
                turn_id=turn_id,
                parent_sequence=parent_sequence,
                tool_call_id=tool_call_id,
                tool=tool,
                args=args,
            ),
            source_step_id=scope.agent_id,
            idempotency_key="tool_call:1",
            created_at="2026-05-15T00:00:00Z",
        )

    def append_tool_result(
        self,
        *,
        scope: AgentRunScope,
        turn_id: str,
        parent_sequence: int | None,
        tool_call_id: str,
        result: ToolResult,
    ) -> AgentContextEntry:
        self.calls.append({"kind": "tool_result", "tool": result.name})
        return AgentContextEntry(
            id="entry-4",
            run_id=scope.run_id,
            context_id=scope.context_id,
            sequence=4,
            entry_type=AgentContextEntryType.TOOL_RESULT,
            payload=AgentToolResultPayload(
                turn_id=turn_id,
                parent_sequence=parent_sequence,
                tool_call_id=tool_call_id,
                tool=result.name,
                status=result.status.value,
                data=result.data,
                text=result.text,
                error=result.error,
            ),
            source_step_id=scope.agent_id,
            idempotency_key="tool_result:1",
            created_at="2026-05-15T00:00:00Z",
        )

    def list_entries(self, *, scope: AgentRunScope) -> list[AgentContextEntry]:
        raise NotImplementedError

    def next_turn_id(self, *, scope: AgentRunScope) -> str:
        raise NotImplementedError
