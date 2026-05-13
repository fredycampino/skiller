from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from skiller.application.agent.config.event_output_sanitizer import (
    AgentEventOutputSanitizer,
)
from skiller.application.agent.config.step_config_reader import AgentStepConfig
from skiller.application.agent.error_mapper import AgentErrorMapper
from skiller.application.agent.feedback import AgentRunnerFeedback
from skiller.application.agent.observer.runtime_event_emitter import AgentRuntimeEventEmitter
from skiller.application.agent.prompt.final_message_extractor import (
    AgentFinalMessageExtractor,
)
from skiller.application.agent.prompt.prompt_builder import AgentPromptBuilder
from skiller.application.agent.tools.tool_manager import ToolManager
from skiller.domain.agent.agent_context_model import (
    AgentContextEntryType,
    AgentUserMessagePayload,
)
from skiller.domain.agent.agent_context_store_port import AgentContextStorePort
from skiller.domain.agent.agent_loop_model import AgentLoop
from skiller.domain.agent.agent_run_model import AgentRunnerFinish
from skiller.domain.agent.llm_model import LLMResponse
from skiller.domain.agent.llm_port import LLMPort
from skiller.domain.tool.tool_contract import ToolConfig
from skiller.domain.tool.tool_execution_model import (
    ToolExecutionRequest,
    ToolExecutionResults,
)
from skiller.domain.tool.tool_execution_port import ToolExecutionPort


@dataclass(frozen=True)
class AgentRunnerRequest:
    run_id: str
    step_id: str
    config: AgentStepConfig


@dataclass(frozen=True)
class AgentRunnerResult:
    final_text: str | None
    turn_count: int
    tool_call_count: int
    finish: AgentRunnerFinish
    response_model: str | None
    error: str | None = None


@dataclass
class AgentRunnerState:
    run_id: str
    agent_id: str
    context_id: str
    config: AgentStepConfig
    enabled_tools: list[ToolConfig]
    final_text: str | None = None
    finish: AgentRunnerFinish | None = None
    response_model: str | None = None
    error: str | None = None
    tool_call_count: int = 0

    @property
    def tools_enabled(self) -> bool:
        return bool(self.config.tools)

    def record_tool_execution(self, results: ToolExecutionResults) -> None:
        self.tool_call_count += results.executed_count()
        if results.is_interrupted():
            self.finish = AgentRunnerFinish.INTERRUPTED
            return
        if results.has_exception():
            self.finish = AgentRunnerFinish.TOOL_EXECUTION_FAILED
            self.error = results.exception_message()
            return
        if not results.items:
            self.finish = AgentRunnerFinish.FINAL

    def record_llm_response(self, response: LLMResponse) -> None:
        self.response_model = response.model


class AgentRunner:
    def __init__(
        self,
        *,
        agent_context_store: AgentContextStorePort,
        llm: LLMPort,
        tool_manager: ToolManager,
        prompt_builder: AgentPromptBuilder,
        final_message_extractor: AgentFinalMessageExtractor,
        error_mapper: AgentErrorMapper,
        feedback: AgentRunnerFeedback,
        event_output_sanitizer: AgentEventOutputSanitizer,
        event_emitter: AgentRuntimeEventEmitter,
        tool_execution: ToolExecutionPort,
    ) -> None:
        self.agent_context_store = agent_context_store
        self.llm = llm
        self.tool_manager = tool_manager
        self.prompt_builder = prompt_builder
        self.final_message_extractor = final_message_extractor
        self.error_mapper = error_mapper
        self.feedback = feedback
        self.event_output_sanitizer = event_output_sanitizer
        self.event_emitter = event_emitter
        self.tool_execution = tool_execution

    def execute(self, request: AgentRunnerRequest) -> AgentRunnerResult:
        state = self._build_runner_state(request)
        self._append_initial_user_task(state=state)

        turn_loop = AgentLoop(max_turns=state.config.max_turns)

        while turn_loop.has_next():
            self._append_last_turn_warning_if_needed(
                state=state,
                turn_loop=turn_loop,
            )
            entries = self.agent_context_store.list_entries(scope=state)
            turn_id = self.agent_context_store.next_turn_id(scope=state)
            llm_request = self.prompt_builder.build_request(
                system=state.config.system,
                entries=entries,
                tools=state.enabled_tools,
            )
            response = self.llm.generate(llm_request)
            if response.ok is False:
                state.finish = AgentRunnerFinish.LLM_REQUEST_FAILED
                state.error = self.error_mapper.llm_request(
                    agent_id=state.agent_id,
                    response=response,
                )
                break
            state.record_llm_response(response)

            if not state.tools_enabled:
                state.final_text = self._append_final_assistant_message(
                    state=state,
                    turn_id=turn_id,
                    content=response.content,
                )
                turn_loop.advance()
                state.finish = AgentRunnerFinish.FINAL
                break

            tool_execution_results = self.tool_execution.execute(
                self._build_tool_execution_request(
                    state=state,
                    turn_id=turn_id,
                    response=response,
                    turn_loop=turn_loop,
                )
            )
            turn_loop.advance()
            state.record_tool_execution(tool_execution_results)
            if state.finish is None:
                continue
            if state.finish == AgentRunnerFinish.FINAL:
                state.final_text = self._append_final_assistant_message(
                    state=state,
                    turn_id=turn_id,
                    content=response.content,
                )
                break
            if state.finish == AgentRunnerFinish.INTERRUPTED:
                self.event_emitter.emit_interrupted(
                    run_id=state.run_id,
                    step_id=state.agent_id,
                    turn_id=turn_id,
                )
                break
            break

        if state.finish is None:
            turn_id = self.agent_context_store.next_turn_id(scope=state)
            self.agent_context_store.append_user_message(
                scope=state,
                turn_id=turn_id,
                text=self.feedback.max_turns_exhausted(),
            )
            state.finish = AgentRunnerFinish.MAX_TURNS_EXHAUSTED
            self.event_emitter.emit_max_turns_exhausted(
                run_id=state.run_id,
                step_id=state.agent_id,
                turn_id=turn_id,
            )

        return AgentRunnerResult(
            final_text=state.final_text,
            turn_count=turn_loop.turn_count,
            tool_call_count=state.tool_call_count,
            finish=state.finish or AgentRunnerFinish.FINAL,
            response_model=state.response_model,
            error=state.error,
        )

    def _build_runner_state(self, request: AgentRunnerRequest) -> AgentRunnerState:
        return AgentRunnerState(
            run_id=request.run_id,
            agent_id=request.step_id,
            context_id=request.config.context_id,
            config=request.config,
            enabled_tools=self._get_enabled_tool_configs(
                agent_id=request.step_id,
                tools=request.config.tools,
            ),
        )

    def _append_initial_user_task(
        self,
        *,
        state: AgentRunnerState,
    ) -> None:
        self.agent_context_store.append_user_message(
            scope=state,
            turn_id=self.agent_context_store.next_turn_id(scope=state),
            text=state.config.task,
        )

    def _build_tool_execution_request(
        self,
        *,
        state: AgentRunnerState,
        turn_id: str,
        response: Any,
        turn_loop: AgentLoop,
    ) -> ToolExecutionRequest:
        return ToolExecutionRequest(
            run_id=state.run_id,
            step_id=state.agent_id,
            context_id=state.context_id,
            turn_id=turn_id,
            response=response,
            allowed_tools=state.config.tools,
            max_tool_calls=state.config.max_tool_calls,
            turn_loop=turn_loop,
        )

    def _append_final_assistant_message(
        self,
        *,
        state: AgentRunnerState,
        turn_id: str,
        content: str | None,
    ) -> str:
        final_text = self.final_message_extractor.extract_final_message(
            step_id=state.agent_id,
            content=content,
        )
        assistant_message_entry = self.agent_context_store.append_assistant_message(
            scope=state,
            turn_id=turn_id,
            message_type="final",
            text=final_text,
        )
        self.event_emitter.emit_assistant_message(
            run_id=state.run_id,
            step_id=state.agent_id,
            turn_id=turn_id,
            sequence=assistant_message_entry.sequence,
            message_type="final",
            text=self._sanitize_assistant_text(final_text),
        )
        return final_text

    def _sanitize_assistant_text(self, text: str) -> str:
        sanitized = self.event_output_sanitizer.sanitize_output(
            {"text": text, "value": None, "body_ref": None}
        )
        return str(sanitized.get("text", ""))

    def _append_last_turn_warning_if_needed(
        self,
        *,
        state: AgentRunnerState,
        turn_loop: AgentLoop,
    ) -> None:
        if not state.tools_enabled:
            return
        remaining_turns = turn_loop.max_turns - turn_loop.turn_count
        if remaining_turns != 1:
            return
        entries = self.agent_context_store.list_entries(scope=state)
        warning = self.feedback.last_turn_warning()
        if any(
            entry.entry_type == AgentContextEntryType.USER_MESSAGE
            and entry.source_step_id == state.agent_id
            and isinstance(entry.payload, AgentUserMessagePayload)
            and entry.payload.text == warning
            for entry in entries
        ):
            return
        self.agent_context_store.append_user_message(
            scope=state,
            turn_id=self.agent_context_store.next_turn_id(scope=state),
            text=warning,
        )

    def _get_enabled_tool_configs(
        self,
        *,
        agent_id: str,
        tools: list[str],
    ) -> list[ToolConfig]:
        if not tools:
            return []
        return self.tool_manager.get_tool_configs(tools)
