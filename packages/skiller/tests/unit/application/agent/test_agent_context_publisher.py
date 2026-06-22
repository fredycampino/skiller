from uuid import UUID

import pytest

from skiller.application.agent.context.agent_context_publisher import (
    AgentContextPublisher,
)
from skiller.application.agent.mapper.feedback import AgentRunnerFeedback
from skiller.domain.agent.agent_config_model import (
    AgentEventOutputConfig,
    AgentEventOutputTruncateConfig,
)
from skiller.domain.agent.agent_context_model import (
    AgentAssistantMessagePayload,
    AgentAssistantMessageType,
    AgentContextEntry,
    AgentContextEntryType,
    AgentContextUsageMarker,
    AgentToolCallPayload,
    AgentToolResultPayload,
    AgentUserMessagePayload,
)
from skiller.domain.agent.agent_context_store_port import AgentContextStorePort
from skiller.domain.agent.agent_llm_provider_model import AgentFakeLLMModel
from skiller.domain.agent.agent_loop_model import AgentLoop
from skiller.domain.agent.agent_run_identity import AgentContext, AgentRun
from skiller.domain.agent.llm_model import (
    LLMResponse,
    LLMToolCall,
    LLMToolCallFunction,
    LLMUsage,
)
from skiller.domain.run.run_model import RunAgent
from skiller.domain.tool.tool_contract import ToolResult, ToolResultStatus, ToolRuntimeConfigs
from skiller.domain.tool.tool_execution_model import (
    AgentToolCall,
    AgentToolResult,
    ToolExecutionRequest,
)

pytestmark = pytest.mark.unit


def test_agent_context_publisher_publishes_tool_entries_with_normalized_data() -> None:
    store = _FakeAgentContextStore()
    publisher = AgentContextPublisher(store, _FakeRunAgentStore(), AgentRunnerFeedback())
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
    publisher = AgentContextPublisher(store, _FakeRunAgentStore(), AgentRunnerFeedback())
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
    run_agent_store = _FakeRunAgentStore()
    run_agent_store.agents[("run-1", "agent-1")] = RunAgent(
        agent_id="agent-1",
        context_id="ctx-1",
        window_start_sequence=1,
        window_base=True,
    )
    publisher = AgentContextPublisher(store, run_agent_store, AgentRunnerFeedback())
    request = _tool_request()
    usage = LLMUsage(prompt_tokens=10, completion_tokens=3, total_tokens=13)

    entry = publisher.publish_final_assistant_message(
        context=request.context,
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
        "delta_tokens": 10,
        "window_start_sequence": 1,
        "window_base": True,
    }


def test_agent_context_publisher_uses_window_estimate_for_base_delta() -> None:
    store = _FakeAgentContextStore(
        marker=AgentContextUsageMarker(
            sequence=249,
            prompt_tokens=80_048,
            delta_tokens=317,
            window_start_sequence=1,
            window_base=False,
        ),
        estimated_tokens=77_636,
    )
    run_agent_store = _FakeRunAgentStore()
    run_agent_store.agents[("run-1", "agent-1")] = RunAgent(
        agent_id="agent-1",
        context_id="ctx-1",
        window_start_sequence=3,
        window_base=True,
    )
    publisher = AgentContextPublisher(store, run_agent_store, AgentRunnerFeedback())
    request = _tool_request()

    publisher.publish_tool_calls_assistant_message(
        context=request.context,
        turn_id="turn-153",
        text="Create branch",
        usage=LLMUsage(
            prompt_tokens=81_624,
            completion_tokens=194,
            total_tokens=81_818,
        ),
    )

    assert store.estimate_calls == [
        {
            "context_id": "ctx-1",
            "start_sequence": 3,
        }
    ]
    assert store.calls[-1]["delta_tokens"] == 3_988
    assert store.calls[-1]["window_start_sequence"] == 3
    assert store.calls[-1]["window_base"] is True


def test_agent_context_publisher_attaches_agent_context_once() -> None:
    store = _FakeAgentContextStore()
    run_agent_store = _FakeRunAgentStore()
    publisher = AgentContextPublisher(store, run_agent_store, AgentRunnerFeedback())
    agent = AgentRun(run_id="run-1", agent_id="agent-1")

    context = publisher.attach_context(agent=agent)
    repeated_context = publisher.attach_context(agent=agent)

    UUID(context.context_id)
    assert context.run_id == "run-1"
    assert context.agent_id == "agent-1"
    assert repeated_context == context

    assert run_agent_store.get_calls == [
        {
            "run_id": "run-1",
            "agent_id": "agent-1",
        }
    ]
    assert run_agent_store.attach_calls == [
        {
            "run_id": "run-1",
            "agent_id": "agent-1",
            "context_id": context.context_id,
        }
    ]


def _tool_request() -> ToolExecutionRequest:
    return ToolExecutionRequest(
        context=AgentContext(
            run_id="run-1",
            agent_id="agent-1",
            context_id="ctx-1",
        ),
        turn_id="turn-1",
        response=LLMResponse(ok=True, model=AgentFakeLLMModel.MODEL1),
        allowed_tools=["notify"],
        runtime_configs=ToolRuntimeConfigs(),
        event_config=_event_output_config(),
        max_tool_calls=5,
        turn_loop=AgentLoop(max_turns=10),
    )


def _event_output_config() -> AgentEventOutputConfig:
    return AgentEventOutputConfig(
        truncate=AgentEventOutputTruncateConfig(
            enabled=True,
            max_text_chars=100,
            max_json_chars=1000,
            max_array_items=10,
        ),
    )


class _FakeAgentContextStore(AgentContextStorePort):
    def __init__(
        self,
        *,
        marker: AgentContextUsageMarker | None = None,
        estimated_tokens: int = 0,
    ) -> None:
        self.calls: list[dict[str, object]] = []
        self.marker = marker
        self.estimated_tokens = estimated_tokens
        self.estimate_calls: list[dict[str, object]] = []

    def init_db(self) -> None:
        raise NotImplementedError

    def append_user_message(
        self,
        *,
        context: AgentContext,
        text: str,
    ) -> AgentContextEntry:
        self.calls.append({"kind": "user", "text": text})
        return AgentContextEntry(
            id=f"entry-{len(self.calls)}",
            run_id=context.run_id,
            context_id=context.context_id,
            sequence=1,
            entry_type=AgentContextEntryType.USER_MESSAGE,
            usage=None,
            payload=AgentUserMessagePayload(text=text),
            source_step_id=context.agent_id,
            created_at="2026-05-15T00:00:00Z",
        )

    def append_tool_calls_assistant_message(
        self,
        *,
        context: AgentContext,
        turn_id: str,
        text: str,
        usage: LLMUsage | None = None,
        delta_tokens: int = 0,
        window_start_sequence: int = 0,
        window_base: bool = False,
    ) -> AgentContextEntry:
        self.calls.append(
            {
                "kind": "assistant",
                "turn_id": turn_id,
                "message_type": AgentAssistantMessageType.TOOL_CALLS.value,
                "text": text,
                "usage": usage,
                "delta_tokens": delta_tokens,
                "window_start_sequence": window_start_sequence,
                "window_base": window_base,
            }
        )
        return AgentContextEntry(
            id=f"entry-{len(self.calls)}",
            run_id=context.run_id,
            context_id=context.context_id,
            sequence=2,
            entry_type=AgentContextEntryType.ASSISTANT_MESSAGE,
            usage=usage,
            message_type=AgentAssistantMessageType.TOOL_CALLS,
            window_start_sequence=window_start_sequence,
            delta_tokens=delta_tokens,
            window_base=window_base,
            payload=AgentAssistantMessagePayload(
                turn_id=turn_id,
                message_type=AgentAssistantMessageType.TOOL_CALLS,
                text=text,
            ),
            source_step_id=context.agent_id,
            created_at="2026-05-15T00:00:00Z",
        )

    def append_final_assistant_message(
        self,
        *,
        context: AgentContext,
        turn_id: str,
        text: str,
        usage: LLMUsage | None,
        delta_tokens: int,
        window_start_sequence: int,
        window_base: bool,
    ) -> AgentContextEntry:
        self.calls.append(
            {
                "kind": "assistant",
                "turn_id": turn_id,
                "message_type": AgentAssistantMessageType.FINAL.value,
                "text": text,
                "usage": usage,
                "delta_tokens": delta_tokens,
                "window_start_sequence": window_start_sequence,
                "window_base": window_base,
            }
        )
        return AgentContextEntry(
            id=f"entry-{len(self.calls)}",
            run_id=context.run_id,
            context_id=context.context_id,
            sequence=2,
            entry_type=AgentContextEntryType.ASSISTANT_MESSAGE,
            usage=usage,
            message_type=AgentAssistantMessageType.FINAL,
            window_start_sequence=window_start_sequence,
            delta_tokens=delta_tokens,
            window_base=window_base,
            payload=AgentAssistantMessagePayload(
                turn_id=turn_id,
                message_type=AgentAssistantMessageType.FINAL,
                text=text,
            ),
            source_step_id=context.agent_id,
            created_at="2026-05-15T00:00:00Z",
        )

    def append_tool_call(
        self,
        *,
        context: AgentContext,
        tool_call: AgentToolCall,
    ) -> AgentContextEntry:
        self.calls.append(
            {"kind": "tool_call", "tool": tool_call.tool, "args": tool_call.args}
        )
        return AgentContextEntry(
            id=f"entry-{len(self.calls)}",
            run_id=context.run_id,
            context_id=context.context_id,
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
            source_step_id=context.agent_id,
            created_at="2026-05-15T00:00:00Z",
        )

    def append_tool_result(
        self,
        *,
        context: AgentContext,
        tool_result: AgentToolResult,
    ) -> AgentContextEntry:
        result = tool_result.result
        self.calls.append({"kind": "tool_result", "tool": result.name})
        return AgentContextEntry(
            id=f"entry-{len(self.calls)}",
            run_id=context.run_id,
            context_id=context.context_id,
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
                error=result.error,
            ),
            source_step_id=context.agent_id,
            created_at="2026-05-15T00:00:00Z",
        )

    def list_entries(self, *, context_id: str) -> list[AgentContextEntry]:
        _ = context_id
        raise NotImplementedError

    def list_window_entries(
        self,
        *,
        context_id: str,
        window_width_tokens: int,
    ) -> list[AgentContextEntry]:
        _ = context_id, window_width_tokens
        raise NotImplementedError

    def get_last_usage_marker(
        self,
        *,
        context_id: str,
    ) -> AgentContextUsageMarker | None:
        _ = context_id
        return self.marker

    def estimate_window_tokens(
        self,
        *,
        context_id: str,
        start_sequence: int,
    ) -> int:
        self.estimate_calls.append(
            {
                "context_id": context_id,
                "start_sequence": start_sequence,
            }
        )
        return self.estimated_tokens

    def next_turn_id(self, *, context_id: str) -> str:
        _ = context_id
        raise NotImplementedError


class _FakeRunAgentStore:
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
