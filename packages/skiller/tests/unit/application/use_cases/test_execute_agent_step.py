from pathlib import Path

import pytest
from helpers.agent_config import FakeAgentConfigPort
from helpers.agent_config import agent_config as agent_config_factory
from helpers.agent_runner import build_agent_runner

from skiller.application.agent.config.agent_step_mapper import AgentStepMapper
from skiller.application.agent.config.step_config_reader import (
    AGENT_RUNTIME_SYSTEM,
    AgentStepConfigReader,
)
from skiller.application.agent.mapper.agent_step_execution_mapper import (
    AgentStepExecutionMapper,
)
from skiller.application.agent.tools.tool_manager import PreparedTool, ToolPrepareResult
from skiller.application.agent.tools.tool_manager_model import AgentToolRequest
from skiller.application.use_cases.execute.execute_agent_step import (
    ExecuteAgentStepUseCase,
)
from skiller.domain.agent.agent_config_validation_model import (
    AgentConfigValidation,
    AgentConfigValidationErrorCode,
)
from skiller.domain.agent.agent_context_model import (
    AgentAssistantMessageType,
    AgentContextEntry,
    AgentContextEntryType,
    AgentContextUsageMarker,
)
from skiller.domain.agent.agent_llm_provider_model import AgentFakeLLMModel, AgentLLMProviderType
from skiller.domain.agent.agent_run_identity import AgentContext
from skiller.domain.agent.agent_run_model import AgentStopReason
from skiller.domain.agent.agent_stats_model import (
    AgentContextObservedStats,
    AgentContextObservedWindowStats,
)
from skiller.domain.agent.llm_model import (
    LLMAssistantMessage,
    LLMMessage,
    LLMResponse,
    LLMToolCall,
    LLMToolCallFunction,
    LLMToolMessage,
    LLMUsage,
    LLMUserMessage,
)
from skiller.domain.agent.llm_request import LLMRequest
from skiller.domain.event.event_model import (
    RuntimeEventPayload,
    RuntimeEventType,
    runtime_event_payload_to_dict,
)
from skiller.domain.run.run_context_model import RunContext
from skiller.domain.run.run_model import Run, RunStatus
from skiller.domain.run.steering_model import (
    SteeringAgentInterrupt,
    SteeringAgentMessage,
    SteeringItem,
    SteeringItemType,
)
from skiller.domain.step.current_step_model import CurrentStep
from skiller.domain.step.step_execution_model import (
    AgentFinalOutputData,
    AgentOutput,
    AgentStopOutputData,
    AgentUsageOutput,
)
from skiller.domain.step.step_execution_result_model import StepExecutionStatus
from skiller.domain.step.step_type import StepType
from skiller.domain.tool.tool_contract import (
    ToolDefinition,
    ToolInput,
    ToolRequest,
    ToolRequestResult,
    ToolResult,
    ToolResultStatus,
    ToolRuntimeConfigs,
    ToolSchema,
)
from skiller.domain.tool.tool_execution_model import AgentToolCall, AgentToolResult

pytestmark = pytest.mark.unit


def _assert_system_message_contains(
    message: LLMMessage,
    *,
    step_system: str,
) -> None:
    assert message.role.value == "system"
    assert AGENT_RUNTIME_SYSTEM in (message.content or "")
    assert step_system in (message.content or "")


class _FakeStore:
    def __init__(self) -> None:
        self.updated: list[dict[str, object]] = []

    def get_run(self, run_id: str) -> Run:
        return Run(
            id=run_id,
            source="internal",
            ref="demo",
            snapshot={"start": "support_agent", "steps": []},
            status=RunStatus.RUNNING.value,
            current="support_agent",
            context=RunContext(inputs={}, step_executions={}),
            created_at="2026-03-07 10:00:00",
            updated_at="2026-03-07 10:00:00",
        )

    def update_run(self, run_id: str, *, status=None, current=None, context=None) -> None:  # noqa: ANN001
        self.updated.append(
            {
                "run_id": run_id,
                "status": status,
                "current": current,
                "context": context,
            }
        )


class _FakeSkillRunner:
    def resolve_file_path(
        self,
        source: str,
        ref: str,
        file_ref: str,
    ) -> Path:
        _ = (source, ref, file_ref)
        return Path("__missing__/agent.json")


class _FakeAgentContextStore:
    def __init__(self, entries: list[AgentContextEntry] | None = None) -> None:
        self.entries = list(entries or [])
        self.appended: list[dict[str, object]] = []

    def init_db(self) -> None:
        return None

    def append_user_message(
        self,
        *,
        context: AgentContext,
        text: str,
    ) -> AgentContextEntry:
        return self._append_entry(
            run_id=context.run_id,
            context_id=context.context_id,
            entry_type=AgentContextEntryType.USER_MESSAGE,
            payload={"type": "user_message", "text": text},
            source_step_id=context.agent_id,
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
        return self._append_entry(
            run_id=context.run_id,
            context_id=context.context_id,
            entry_type=AgentContextEntryType.ASSISTANT_MESSAGE,
            payload={
                "type": "assistant_message",
                "turn_id": turn_id,
                "message_type": AgentAssistantMessageType.TOOL_CALLS.value,
                "text": text,
            },
            usage=usage,
            message_type=AgentAssistantMessageType.TOOL_CALLS,
            window_start_sequence=window_start_sequence,
            delta_tokens=delta_tokens,
            window_base=window_base,
            source_step_id=context.agent_id,
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
        return self._append_entry(
            run_id=context.run_id,
            context_id=context.context_id,
            entry_type=AgentContextEntryType.ASSISTANT_MESSAGE,
            payload={
                "type": "assistant_message",
                "turn_id": turn_id,
                "message_type": AgentAssistantMessageType.FINAL.value,
                "text": text,
            },
            usage=usage,
            message_type=AgentAssistantMessageType.FINAL,
            window_start_sequence=window_start_sequence,
            delta_tokens=delta_tokens,
            window_base=window_base,
            source_step_id=context.agent_id,
        )

    def append_tool_call(
        self,
        *,
        context: AgentContext,
        tool_call: AgentToolCall,
    ) -> AgentContextEntry:
        return self._append_entry(
            run_id=context.run_id,
            context_id=context.context_id,
            entry_type=AgentContextEntryType.TOOL_CALL,
            payload={
                "type": "tool_call",
                "turn_id": tool_call.turn_id,
                "parent_sequence": tool_call.parent_sequence,
                "tool_call_id": tool_call.tool_call_id,
                "tool": tool_call.tool,
                "args": tool_call.args,
            },
            source_step_id=context.agent_id,
        )

    def append_tool_result(
        self,
        *,
        context: AgentContext,
        tool_result: AgentToolResult,
    ) -> AgentContextEntry:
        result = tool_result.result
        return self._append_entry(
            run_id=context.run_id,
            context_id=context.context_id,
            entry_type=AgentContextEntryType.TOOL_RESULT,
            payload={
                "type": "tool_result",
                "turn_id": tool_result.turn_id,
                "parent_sequence": tool_result.parent_sequence,
                "tool_call_id": tool_result.tool_call_id,
                "tool": result.name,
                "status": result.status.value,
                "data": result.data,
                "error": result.error,
            },
            source_step_id=context.agent_id,
        )

    def _append_entry(
        self,
        *,
        run_id: str,
        context_id: str,
        entry_type: AgentContextEntryType,
        payload: dict[str, object],
        usage: LLMUsage | None = None,
        message_type: AgentAssistantMessageType | None = None,
        window_start_sequence: int | None = None,
        delta_tokens: int | None = None,
        window_base: bool | None = None,
        source_step_id: str,
    ) -> AgentContextEntry:
        self.appended.append(
            {
                "run_id": run_id,
                "context_id": context_id,
                "entry_type": entry_type,
                "payload": payload,
                "message_type": message_type.value if message_type else None,
                "window_start_sequence": window_start_sequence,
                "delta_tokens": delta_tokens,
                "window_base": window_base,
                "source_step_id": source_step_id,
            }
        )
        entry = AgentContextEntry(
            id=f"entry-{len(self.entries) + 1}",
            run_id=run_id,
            context_id=context_id,
            sequence=len(self.entries) + 1,
            entry_type=entry_type,
            payload=payload,
            usage=usage,
            message_type=message_type,
            window_start_sequence=window_start_sequence,
            delta_tokens=delta_tokens,
            window_base=window_base,
            source_step_id=source_step_id,
            created_at="2026-04-22T00:00:00Z",
        )
        self.entries.append(entry)
        return entry

    def list_entries(self, *, context_id: str) -> list[AgentContextEntry]:
        return [
            entry
            for entry in self.entries
            if entry.context_id == context_id
        ]

    def list_window_entries(
        self,
        *,
        context_id: str,
        window_width_tokens: int,
    ) -> list[AgentContextEntry]:
        _ = window_width_tokens
        return self.list_entries(context_id=context_id)

    def get_last_usage_marker(
        self,
        *,
        context_id: str,
    ) -> AgentContextUsageMarker | None:
        entries = [
            entry
            for entry in self.entries
            if entry.context_id == context_id
        ]
        for entry in reversed(entries):
            if entry.usage is None:
                continue
            if entry.usage.prompt_tokens is None:
                continue
            if entry.delta_tokens is None:
                continue
            if entry.window_start_sequence is None:
                continue
            if entry.window_base is None:
                continue
            return AgentContextUsageMarker(
                sequence=entry.sequence,
                prompt_tokens=entry.usage.prompt_tokens,
                delta_tokens=entry.delta_tokens,
                window_start_sequence=entry.window_start_sequence,
                window_base=entry.window_base,
            )
        return None

    def get_stats(self, *, context_id: str) -> AgentContextObservedStats:
        _ = context_id
        return AgentContextObservedStats(
            entries=0,
            estimated_tokens=0,
            window=AgentContextObservedWindowStats(
                start_sequence=0,
                end_sequence=0,
                current_tokens=0,
            ),
        )

    def next_turn_id(self, *, context_id: str) -> str:
        entries = self.list_entries(context_id=context_id)
        turn_entries = sum(
            1
            for entry in entries
            if entry.entry_type
            in {
                AgentContextEntryType.ASSISTANT_MESSAGE,
                AgentContextEntryType.TOOL_CALL,
            }
        )
        return f"turn-{turn_entries + 1}"


class _FakeLLM:
    def __init__(
        self,
        response: object | None = None,
        responses: list[object] | None = None,
    ) -> None:
        self.response = response or {"ok": True, "content": "Hello back.", "model": "model1"}
        self.responses = list(responses or [])
        self.calls: list[LLMRequest] = []

    def generate(self, request: LLMRequest) -> LLMResponse:
        self.calls.append(request)
        if self.responses:
            return self._to_llm_response(self.responses.pop(0))
        return self._to_llm_response(self.response)

    def _to_llm_response(self, value: object) -> LLMResponse:
        if isinstance(value, LLMResponse):
            return value
        if isinstance(value, dict):
            return LLMResponse(
                ok=bool(value.get("ok")),
                content=value.get("content") if isinstance(value.get("content"), str) else (
                    None if value.get("content") is None else str(value.get("content"))
                ),
                model=AgentFakeLLMModel.MODEL1,
                error=value.get("error") if isinstance(value.get("error"), str) else None,
            )
        return LLMResponse(ok=True, content=str(value), model=AgentFakeLLMModel.MODEL1)


class _FakeTool(ToolDefinition[ToolRequest]):
    def __init__(self, name: str) -> None:
        self.name = name
        self.description = f"Fake {name} tool"

    def schema(self) -> ToolSchema:
        return ToolSchema(value={})

    def request(self, input: ToolInput) -> ToolRequestResult[ToolRequest]:
        return ToolRequestResult.valid(ToolRequest())


class _FakeToolManager:
    def __init__(
        self,
        *,
        execute_result: ToolResult | None = None,
    ) -> None:
        self.execute_result = execute_result or ToolResult(
            name="notify",
            status=ToolResultStatus.COMPLETED,
            data={"message": "ok"},
            text="ok",
            error=None,
        )
        self.get_tool_definitions_calls: list[list[str]] = []
        self.execute_prepared_calls: list[PreparedTool] = []

    def get_tool_definitions(self, allowed_tools: list[str]) -> list[ToolDefinition]:
        self.get_tool_definitions_calls.append(list(allowed_tools))
        return [_FakeTool(name=tool) for tool in allowed_tools]

    def get_tools(self, allowed_tools: list[str]) -> list[_FakeTool]:
        return [_FakeTool(name=tool) for tool in allowed_tools]

    def prepare(self, request: AgentToolRequest) -> ToolPrepareResult:
        return ToolPrepareResult(
            ok=True,
            tool_name=request.tool,
            prepared=PreparedTool(
                name=request.tool,
                tool=_FakeTool(request.tool),
                request=request,
                config=request.runtime_config,
            ),
        )

    def execute_prepared(self, prepared: PreparedTool) -> ToolResult:
        request = prepared.request
        if not isinstance(request, AgentToolRequest):
            raise AssertionError("expected AgentToolRequest")
        self.execute_prepared_calls.append(prepared)
        if callable(self.execute_result):
            return self.execute_result(request)
        return self.execute_result


class _FakeSteering:
    def __init__(self, consume_results: list[bool] | None = None) -> None:
        self.consume_results = list(consume_results or [])

    def append(self, run_id: str, item: SteeringItem) -> None:
        return None

    def pop(self, run_id: str, item_type: SteeringItemType) -> list[SteeringItem]:
        if item_type is SteeringAgentInterrupt and self.consume_results:
            if self.consume_results.pop(0):
                return [SteeringAgentInterrupt()]
            return []
        if item_type is SteeringAgentMessage:
            return []
        return []


class _FakeAppendRuntimeEventUseCase:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def execute(
        self,
        run_id: str,
        *,
        event_type: RuntimeEventType,
        payload: RuntimeEventPayload | dict[str, object] | None = None,
        step_id: str | None = None,
        step_type=None,  # noqa: ANN001
        agent_sequence: int | None = None,
        execution=None,  # noqa: ANN001
        next_step_id: str | None = None,
        error: str | None = None,
    ) -> None:
        self.calls.append(
            {
                "run_id": run_id,
                "event_type": event_type,
                "payload": (
                    runtime_event_payload_to_dict(payload)
                    if payload is not None
                    else None
                ),
                "step_id": step_id,
                "step_type": step_type,
                "agent_sequence": agent_sequence,
                "execution": execution,
                "next_step_id": next_step_id,
                "error": error,
            }
        )


def _build_use_case(
    *,
    store: _FakeStore,
    context_store: _FakeAgentContextStore,
    llm: _FakeLLM,
    steering: _FakeSteering | None = None,
    tool_manager: _FakeToolManager | None = None,
    agent_config: FakeAgentConfigPort | None = None,
    append_runtime_event_use_case: _FakeAppendRuntimeEventUseCase | None = None,
) -> ExecuteAgentStepUseCase:
    resolved_tool_manager = tool_manager or _FakeToolManager()
    resolved_agent_config = agent_config or FakeAgentConfigPort(
        config=agent_config_factory(
            tools=ToolRuntimeConfigs(),
        ),
    )
    runner = build_agent_runner(
        agent_context_store=context_store,
        steering=steering,
        llm=llm,
        tool_manager=resolved_tool_manager,
        append_runtime_event_use_case=append_runtime_event_use_case,
    )
    return ExecuteAgentStepUseCase(
        store=store,
        runner=runner,
        step_mapper=AgentStepMapper(),
        config_reader=AgentStepConfigReader(
            agent_config=resolved_agent_config,
            run_store=store,
            skill_runner=_FakeSkillRunner(),
            tool_manager=resolved_tool_manager,
        ),
        execution_mapper=AgentStepExecutionMapper(),
    )


def test_execute_agent_step_advances_with_config_error_when_agent_config_is_invalid() -> None:
    store = _FakeStore()
    context_store = _FakeAgentContextStore()
    llm = _FakeLLM()
    context = RunContext(inputs={}, step_executions={})
    validation = AgentConfigValidation.invalid(
        error=AgentConfigValidationErrorCode.PROVIDER_MODEL_UNSUPPORTED,
        message="Provider 'minimax' does not support model='bad-model'.",
    )
    agent_config = FakeAgentConfigPort(validation=validation)
    use_case = _build_use_case(
        store=store,
        context_store=context_store,
        llm=llm,
        agent_config=agent_config,
    )

    result = use_case.execute(
        CurrentStep(
            run_id="run-1",
            step_index=0,
            step_id="support_agent",
            step_type=StepType.AGENT,
            step={
                "system": "Be useful.",
                "task": "Hi",
                "tools": ["notify"],
                "next": "ask_user",
            },
            context=context,
        )
    )

    assert result.status == StepExecutionStatus.NEXT
    assert result.next_step_id == "ask_user"
    assert result.execution is not None
    assert result.execution.output == AgentOutput(
        text="Provider 'minimax' does not support model='bad-model'.",
        text_ref="data.message",
        data=AgentStopOutputData(
            stop_reason=AgentStopReason.CONFIG_INVALID,
            context_id="",
            message=(
                "Provider 'minimax' does not support model='bad-model'. "
                "(PROVIDER_MODEL_UNSUPPORTED)"
            ),
            turn_count=0,
            tool_call_count=0,
        ),
    )
    assert context.step_executions["support_agent"] == result.execution
    assert llm.calls == []
    assert context_store.appended == []
    assert store.updated == [
        {
            "run_id": "run-1",
            "status": RunStatus.RUNNING,
            "current": "ask_user",
            "context": context,
        }
    ]


def test_execute_agent_step_appends_context_and_moves_to_next() -> None:
    store = _FakeStore()
    context_store = _FakeAgentContextStore()
    llm = _FakeLLM()
    use_case = _build_use_case(
        store=store,
        context_store=context_store,
        llm=llm,
    )
    context = RunContext(inputs={}, step_executions={})

    result = use_case.execute(
        CurrentStep(
            run_id="run-1",
            step_index=0,
            step_id="support_agent",
            step_type=StepType.AGENT,
            step={
                "system": "Be useful.",
                "task": "Hi",
                "max_turns": 1,
                "next": "send_reply",
            },
            context=context,
        )
    )

    assert result.status == StepExecutionStatus.NEXT
    assert result.next_step_id == "send_reply"
    assert result.execution is not None
    assert isinstance(result.execution.output.data, AgentFinalOutputData)
    context_id = result.execution.output.data.context_id
    assert isinstance(context_id, str)
    assert context_id
    assert result.execution.output == AgentOutput(
        text="Hello back.",
        text_ref="data.final",
        data=AgentFinalOutputData(
            stop_reason=AgentStopReason.FINAL,
            context_id=context_id,
            final="Hello back.",
            turn_count=1,
            tool_call_count=0,
        ),
    )
    assert context.step_executions["support_agent"] == result.execution
    assert context_store.appended[0]["entry_type"] == AgentContextEntryType.USER_MESSAGE
    assert context_store.appended[0]["payload"] == {"type": "user_message", "text": "Hi"}
    assert context_store.appended[1]["entry_type"] == AgentContextEntryType.ASSISTANT_MESSAGE
    assert context_store.appended[1]["payload"] == {
        "type": "assistant_message",
        "turn_id": "turn-1",
        "message_type": "final",
        "text": "Hello back.",
    }
    assert len(llm.calls) == 1
    _assert_system_message_contains(llm.calls[0].messages[0], step_system="Be useful.")
    assert llm.calls[0].messages[1:] == (LLMUserMessage("Hi"),)
    assert llm.calls[0].tools == ()
    assert store.updated == [
        {
            "run_id": "run-1",
            "status": RunStatus.RUNNING,
            "current": "send_reply",
            "context": context,
        }
    ]


def test_execute_agent_step_supports_tool_call_then_success() -> None:
    llm = _FakeLLM(
        responses=[
            LLMResponse(
                ok=True,
                model=AgentFakeLLMModel.MODEL1,
                tool_calls=(
                    LLMToolCall(
                        id="openai-call-1",
                        function=LLMToolCallFunction(
                            name="notify",
                            arguments_json='{"message":"hello"}',
                        ),
                    ),
                ),
                finish_reason="tool_calls",
            ),
            LLMResponse(
                ok=True,
                content="Done.",
                model=AgentFakeLLMModel.MODEL1,
                usage=LLMUsage(
                    prompt_tokens=100,
                    completion_tokens=25,
                    total_tokens=125,
                ),
            ),
        ]
    )
    tool_manager = _FakeToolManager(
        execute_result=ToolResult(
            name="notify",
            status=ToolResultStatus.COMPLETED,
            data={"message": "sent"},
            text="sent",
            error=None,
        )
    )
    use_case = _build_use_case(
        store=_FakeStore(),
        context_store=_FakeAgentContextStore(),
        llm=llm,
        tool_manager=tool_manager,
    )

    result = use_case.execute(
        CurrentStep(
            run_id="run-1",
            step_index=0,
            step_id="support_agent",
            step_type=StepType.AGENT,
            step={
                "system": "Be useful.",
                "task": "Hi",
                "tools": ["notify"],
                "max_turns": 3,
            },
            context=RunContext(inputs={}, step_executions={}),
        )
    )

    assert result.status == StepExecutionStatus.COMPLETED
    assert result.execution is not None
    assert isinstance(result.execution.output.data, AgentFinalOutputData)
    context_id = result.execution.output.data.context_id
    assert isinstance(context_id, str)
    assert context_id
    assert result.execution.output == AgentOutput(
        text="Done.",
        text_ref="data.final",
        data=AgentFinalOutputData(
            stop_reason=AgentStopReason.FINAL,
            context_id=context_id,
            final="Done.",
            turn_count=2,
            tool_call_count=1,
                usage=AgentUsageOutput(
                    prompt_tokens=100,
                    completion_tokens=25,
                    total_tokens=125,
                    provider=AgentLLMProviderType.FAKE,
                    model=AgentFakeLLMModel.MODEL1,
                ),
        ),
    )
    assert tool_manager.get_tool_definitions_calls == [["notify"]]
    executed_requests = [
        prepared.request for prepared in tool_manager.execute_prepared_calls
    ]
    assert executed_requests == [
        AgentToolRequest(
            run_id="run-1",
            step_id="support_agent",
            context_id=context_id,
            turn_id="turn-1",
            tool_call_id="openai-call-1",
            tool="notify",
            args={"message": "hello"},
            allowed_tools=["notify"],
            runtime_config=None,
        )
    ]
    assert len(llm.calls) == 2
    _assert_system_message_contains(llm.calls[0].messages[0], step_system="Be useful.")
    assert llm.calls[0].messages[1:] == (LLMUserMessage("Hi"),)
    assert [tool.name for tool in llm.calls[0].tools] == ["notify"]
    _assert_system_message_contains(llm.calls[1].messages[0], step_system="Be useful.")
    assert llm.calls[1].messages[1:] == (
        LLMUserMessage("Hi"),
        LLMAssistantMessage(
            tool_calls=(
                LLMToolCall(
                    id="openai-call-1",
                    function=LLMToolCallFunction(
                        name="notify",
                        arguments_json='{"message": "hello"}',
                    ),
                ),
            )
        ),
        LLMToolMessage(
            '{"data": {"message": "sent"}, "status": "COMPLETED", "tool": "notify"}',
            tool_call_id="openai-call-1",
        ),
    )
    assert [tool.name for tool in llm.calls[1].tools] == ["notify"]


def test_execute_agent_step_interrupts_and_advances_to_next_step() -> None:
    store = _FakeStore()
    context_store = _FakeAgentContextStore()
    llm = _FakeLLM(
        response=LLMResponse(
            ok=True,
            model=AgentFakeLLMModel.MODEL1,
            tool_calls=(
                LLMToolCall(
                    id="openai-call-1",
                    function=LLMToolCallFunction(
                        name="notify",
                        arguments_json='{"message":"hello"}',
                    ),
                ),
            ),
            finish_reason="tool_calls",
        )
    )
    use_case = _build_use_case(
        store=store,
        context_store=context_store,
        llm=llm,
        steering=_FakeSteering(consume_results=[True]),
        tool_manager=_FakeToolManager(),
    )
    context = RunContext(inputs={}, step_executions={})

    result = use_case.execute(
        CurrentStep(
            run_id="run-1",
            step_index=0,
            step_id="support_agent",
            step_type=StepType.AGENT,
            step={
                "system": "Be useful.",
                "task": "Hi",
                "max_turns": 2,
                "tools": ["notify"],
                "next": "send_reply",
            },
            context=context,
        )
    )

    assert result.status == StepExecutionStatus.NEXT
    assert result.next_step_id == "send_reply"
    assert result.execution is not None
    assert isinstance(result.execution.output.data, AgentStopOutputData)
    context_id = result.execution.output.data.context_id
    assert isinstance(context_id, str)
    assert context_id
    assert result.execution.output == AgentOutput(
        text="",
        text_ref=None,
        data=AgentStopOutputData(
            stop_reason=AgentStopReason.INTERRUPTED,
            context_id=context_id,
            message="Agent execution interrupted.",
            turn_count=1,
            tool_call_count=0,
        ),
    )
    assert store.updated == [
        {
            "run_id": "run-1",
            "status": RunStatus.RUNNING,
            "current": "send_reply",
            "context": context,
        }
    ]


def test_execute_agent_step_advances_when_agent_reaches_max_turns() -> None:
    store = _FakeStore()
    context_store = _FakeAgentContextStore()
    llm = _FakeLLM(
        responses=[
            LLMResponse(
                ok=True,
                model=AgentFakeLLMModel.MODEL1,
                tool_calls=(
                    LLMToolCall(
                        id="openai-call-1",
                        function=LLMToolCallFunction(
                            name="notify",
                            arguments_json='{"message":"hello"}',
                        ),
                    ),
                ),
                finish_reason="tool_calls",
            )
        ]
    )
    use_case = _build_use_case(
        store=store,
        context_store=context_store,
        llm=llm,
        tool_manager=_FakeToolManager(),
    )
    context = RunContext(inputs={}, step_executions={})

    result = use_case.execute(
        CurrentStep(
            run_id="run-1",
            step_index=0,
            step_id="support_agent",
            step_type=StepType.AGENT,
            step={
                "system": "Be useful.",
                "task": "Hi",
                "max_turns": 1,
                "tools": ["notify"],
                "next": "send_reply",
            },
            context=context,
        )
    )

    assert result.status == StepExecutionStatus.NEXT
    assert result.next_step_id == "send_reply"
    assert result.execution is not None
    assert isinstance(result.execution.output.data, AgentStopOutputData)
    context_id = result.execution.output.data.context_id
    assert isinstance(context_id, str)
    assert context_id
    assert result.execution.output == AgentOutput(
        text="",
        text_ref=None,
        data=AgentStopOutputData(
            stop_reason=AgentStopReason.MAX_TURNS_EXHAUSTED,
            context_id=context_id,
            message="Agent stopped after reaching max turns.",
            turn_count=1,
            tool_call_count=1,
        ),
    )
    assert store.updated == [
        {
            "run_id": "run-1",
            "status": RunStatus.RUNNING,
            "current": "send_reply",
            "context": context,
        }
    ]


def test_execute_agent_step_fails_when_agent_returns_invalid_final_message() -> None:
    store = _FakeStore()
    context_store = _FakeAgentContextStore()
    llm = _FakeLLM(
        responses=[
            LLMResponse(
                ok=True,
                content="   ",
                model=AgentFakeLLMModel.MODEL1,
            )
        ]
    )
    use_case = _build_use_case(
        store=store,
        context_store=context_store,
        llm=llm,
        tool_manager=_FakeToolManager(),
    )
    context = RunContext(inputs={}, step_executions={})

    with pytest.raises(ValueError, match="returned no final answer"):
        use_case.execute(
            CurrentStep(
                run_id="run-1",
                step_index=0,
                step_id="support_agent",
                step_type=StepType.AGENT,
                step={
                    "system": "Be useful.",
                    "task": "Hi",
                    "max_turns": 2,
                    "tools": [],
                    "next": "send_reply",
                },
                context=context,
            )
        )


def test_execute_agent_step_emits_agent_tool_events_from_agent_context_entries() -> None:
    llm = _FakeLLM(
        responses=[
            LLMResponse(
                ok=True,
                model=AgentFakeLLMModel.MODEL1,
                tool_calls=(
                    LLMToolCall(
                        id="openai-call-1",
                        function=LLMToolCallFunction(
                            name="shell",
                            arguments_json='{"command":"Authorization: Bearer abc"}',
                        ),
                    ),
                ),
                finish_reason="tool_calls",
            ),
            LLMResponse(ok=True, content="Done.", model=AgentFakeLLMModel.MODEL1),
        ]
    )
    tool_manager = _FakeToolManager(
        execute_result=ToolResult(
            name="shell",
            status=ToolResultStatus.COMPLETED,
            data={"logs": ["line1", "line2", "line3"], "password": "raw-secret"},
            text="abcdefghijklmnopqrstuvwxyz",
            error=None,
        )
    )
    append_event = _FakeAppendRuntimeEventUseCase()
    use_case = _build_use_case(
        store=_FakeStore(),
        context_store=_FakeAgentContextStore(),
        llm=llm,
        tool_manager=tool_manager,
        append_runtime_event_use_case=append_event,
    )

    use_case.execute(
        CurrentStep(
            run_id="run-1",
            step_index=0,
            step_id="support_agent",
            step_type=StepType.AGENT,
            step={
                "system": "Be useful.",
                "task": "Hi",
                "tools": ["shell"],
                "max_turns": 3,
            },
            context=RunContext(inputs={}, step_executions={}),
        )
    )

    assert append_event.calls[0]["event_type"] == RuntimeEventType.AGENT_TOOL_CALL
    tool_call_payload = append_event.calls[0]["payload"]
    assert isinstance(tool_call_payload, dict)
    assert tool_call_payload["body"]["tool_call_id"] == "openai-call-1"
    assert tool_call_payload["body"]["args"]["command"] == "Authorization: Bearer abc"

    assert append_event.calls[1]["event_type"] == RuntimeEventType.AGENT_TOOL_RESULT
    tool_result_payload = append_event.calls[1]["payload"]
    assert isinstance(tool_result_payload, dict)
    assert tool_result_payload["body"]["tool_call_id"] == "openai-call-1"
    assert tool_result_payload["body"]["text"] == "abcdefghijklmnopqrstuvwxyz"
    assert tool_result_payload["body"]["data"]["password"] == "raw-secret"
    assert tool_result_payload["body"]["data"]["logs"] == [
        "line1",
        "line2",
        "line3",
    ]


def test_execute_agent_step_advances_when_llm_request_fails() -> None:
    store = _FakeStore()
    context = RunContext(inputs={}, step_executions={})
    use_case = _build_use_case(
        store=store,
        context_store=_FakeAgentContextStore(),
        llm=_FakeLLM(
            response=LLMResponse(
                ok=False,
                model=AgentFakeLLMModel.MODEL1,
                error="invalid params",
                error_code="2013",
            )
        ),
    )

    result = use_case.execute(
        CurrentStep(
            run_id="run-1",
            step_index=0,
            step_id="support_agent",
            step_type=StepType.AGENT,
            step={
                "system": "Be useful.",
                "task": "Hi",
                "next": "send_reply",
            },
            context=context,
        )
    )

    assert result.status == StepExecutionStatus.NEXT
    assert result.next_step_id == "send_reply"
    assert result.execution is not None
    assert isinstance(result.execution.output.data, AgentStopOutputData)
    assert result.execution.output.data.stop_reason == AgentStopReason.LLM_REQUEST_FAILED
    assert result.execution.output.data.context_id
    assert (
        result.execution.output.data.message
        == "Agent 'support_agent' LLM request failed: invalid params (error_code=2013)"
    )
    assert context.step_executions["support_agent"] == result.execution
    assert store.updated == [
        {
            "run_id": "run-1",
            "status": RunStatus.RUNNING,
            "current": "send_reply",
            "context": context,
        }
    ]
