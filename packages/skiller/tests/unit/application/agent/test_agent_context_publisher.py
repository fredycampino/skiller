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
    LLMUsage,
)
from skiller.domain.run.run_model import RunAgent
from skiller.domain.tool.tool_contract import ToolResult, ToolResultStatus
from skiller.domain.tool.tool_execution_model import (
    AgentToolCall,
    AgentToolResult,
    ToolExecutionRequest,
)

pytestmark = pytest.mark.unit


def test_agent_context_publisher_publishes_tool_entries_with_normalized_data() -> None:
    store = _FakeAgentContextStore()
    publisher = AgentContextPublisher(store, _FakeRunStore(), AgentRunnerFeedback())
    request = _tool_request()
    tool_call_entry = publisher.publish_tool_call(
        request=request,
        tool_call=AgentToolCall(
            turn_id=request.turn_id,
            tool_call_id="call-1",
            tool="unknown",
            parent_sequence=5,
            args={"command": "pwd"},
        ),
    )
    tool_result_entry = publisher.publish_tool_result(
        request=request,
        tool_result=AgentToolResult(
            turn_id=request.turn_id,
            tool_call_id="call-1",
            parent_sequence=5,
            result=ToolResult(
                name="shell",
                status=ToolResultStatus.COMPLETED,
                data={"stdout": "ok"},
                text="ok",
            ),
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
    publisher = AgentContextPublisher(store, _FakeRunStore(), AgentRunnerFeedback())
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
    assert [call["kind"] for call in store.calls] == ["user", "user", "user"]


def test_agent_context_publisher_passes_assistant_usage_to_store() -> None:
    store = _FakeAgentContextStore()
    publisher = AgentContextPublisher(store, _FakeRunStore(), AgentRunnerFeedback())
    request = _tool_request()
    usage = LLMUsage(prompt_tokens=10, completion_tokens=3, total_tokens=13)

    entry = publisher.publish_final_assistant_message(
        scope=request,
        turn_id="turn-1",
        text="Done.",
        usage=usage,
    )

    assert entry.usage == usage
    assert store.calls[-1] == {
        "kind": "assistant",
        "turn_id": "turn-1",
        "message_type": "final",
        "text": "Done.",
        "usage": usage,
    }


def test_agent_context_publisher_attaches_agent_context_once() -> None:
    store = _FakeAgentContextStore()
    run_store = _FakeRunStore()
    publisher = AgentContextPublisher(store, run_store, AgentRunnerFeedback())
    entry = store.append_user_message(
        scope=_tool_request(),
        text="Hello",
    )

    publisher.attach(entry)
    publisher.attach(entry)

    assert run_store.get_calls == [
        {
            "run_id": "run-1",
            "agent_id": "agent-1",
        }
    ]
    assert run_store.attach_calls == [
        {
            "run_id": "run-1",
            "agent_id": "agent-1",
            "context_id": "ctx-1",
        }
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
        text: str,
    ) -> AgentContextEntry:
        self.calls.append({"kind": "user", "text": text})
        return AgentContextEntry(
            id=f"entry-{len(self.calls)}",
            run_id=scope.run_id,
            context_id=scope.context_id,
            sequence=1,
            entry_type=AgentContextEntryType.USER_MESSAGE,
            usage=None,
            payload=AgentUserMessagePayload(text=text),
            source_step_id=scope.agent_id,
            created_at="2026-05-15T00:00:00Z",
        )

    def append_assistant_message(
        self,
        *,
        scope: AgentRunScope,
        turn_id: str,
        message_type: str,
        text: str,
        usage: LLMUsage | None = None,
    ) -> AgentContextEntry:
        self.calls.append(
            {
                "kind": "assistant",
                "turn_id": turn_id,
                "message_type": message_type,
                "text": text,
                "usage": usage,
            }
        )
        return AgentContextEntry(
            id=f"entry-{len(self.calls)}",
            run_id=scope.run_id,
            context_id=scope.context_id,
            sequence=2,
            entry_type=AgentContextEntryType.ASSISTANT_MESSAGE,
            usage=usage,
            payload=AgentAssistantMessagePayload(
                turn_id=turn_id,
                message_type=message_type,
                text=text,
                total_tokens=usage.total_tokens if usage is not None else None,
            ),
            source_step_id=scope.agent_id,
            created_at="2026-05-15T00:00:00Z",
        )

    def append_tool_call(
        self,
        *,
        scope: AgentRunScope,
        tool_call: AgentToolCall,
    ) -> AgentContextEntry:
        self.calls.append(
            {"kind": "tool_call", "tool": tool_call.tool, "args": tool_call.args}
        )
        return AgentContextEntry(
            id=f"entry-{len(self.calls)}",
            run_id=scope.run_id,
            context_id=scope.context_id,
            sequence=3,
            entry_type=AgentContextEntryType.TOOL_CALL,
            usage=None,
            payload=AgentToolCallPayload(
                turn_id=tool_call.turn_id,
                parent_sequence=tool_call.parent_sequence,
                tool_call_id=tool_call.tool_call_id,
                tool=tool_call.tool,
                args=tool_call.args,
            ),
            source_step_id=scope.agent_id,
            created_at="2026-05-15T00:00:00Z",
        )

    def append_tool_result(
        self,
        *,
        scope: AgentRunScope,
        tool_result: AgentToolResult,
    ) -> AgentContextEntry:
        result = tool_result.result
        self.calls.append({"kind": "tool_result", "tool": result.name})
        return AgentContextEntry(
            id=f"entry-{len(self.calls)}",
            run_id=scope.run_id,
            context_id=scope.context_id,
            sequence=4,
            entry_type=AgentContextEntryType.TOOL_RESULT,
            usage=None,
            payload=AgentToolResultPayload(
                turn_id=tool_result.turn_id,
                parent_sequence=tool_result.parent_sequence,
                tool_call_id=tool_result.tool_call_id,
                tool=result.name,
                status=result.status.value,
                data=result.data,
                text=result.text,
                error=result.error,
            ),
            source_step_id=scope.agent_id,
            created_at="2026-05-15T00:00:00Z",
        )

    def list_entries(self, *, context_id: str) -> list[AgentContextEntry]:
        _ = context_id
        raise NotImplementedError

    def next_turn_id(self, *, context_id: str) -> str:
        _ = context_id
        raise NotImplementedError


class _FakeRunStore:
    def __init__(self) -> None:
        self.agents: dict[tuple[str, str], RunAgent] = {}
        self.attach_calls: list[dict[str, str]] = []
        self.get_calls: list[dict[str, str]] = []

    def get_agent(self, *, run_id: str, agent_id: str) -> RunAgent | None:
        self.get_calls.append({"run_id": run_id, "agent_id": agent_id})
        return self.agents.get((run_id, agent_id))

    def attach_agent(self, *, run_id: str, agent_id: str, context_id: str) -> None:
        self.attach_calls.append(
            {
                "run_id": run_id,
                "agent_id": agent_id,
                "context_id": context_id,
            }
        )
        self.agents[(run_id, agent_id)] = RunAgent(
            agent_id=agent_id,
            context_id=context_id,
        )
