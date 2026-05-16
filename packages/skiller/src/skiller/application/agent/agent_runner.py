from __future__ import annotations

from typing import Any

from skiller.application.agent.context.agent_context_manager import AgentContextManager
from skiller.application.agent.context.agent_context_publisher import (
    AgentContextPublisher,
)
from skiller.application.agent.event.agent_event_publisher import AgentEventPublisher
from skiller.application.agent.mapper.error_mapper import AgentErrorMapper
from skiller.application.agent.mapper.feedback import AgentRunnerFeedback
from skiller.application.agent.runner_state import (
    AgentRunnerRequest,
    AgentRunnerResult,
    AgentRunnerState,
)
from skiller.application.agent.tools.agent_tool_executor import AgentToolExecutor
from skiller.application.agent.tools.tool_manager import ToolManager
from skiller.domain.agent.agent_context_model import (
    AgentContextEntryType,
    AgentUserMessagePayload,
)
from skiller.domain.agent.agent_context_store_port import AgentContextStorePort
from skiller.domain.agent.agent_loop_model import AgentLoop
from skiller.domain.agent.agent_run_model import AgentRunnerFinish
from skiller.domain.agent.llm_port import LLMPort
from skiller.domain.tool.tool_contract import ToolConfig
from skiller.domain.tool.tool_execution_model import (
    ToolExecutionRequest,
)


class AgentRunner:
    def __init__(
        self,
        *,
        agent_context_store: AgentContextStorePort,
        llm: LLMPort,
        tool_manager: ToolManager,
        context_manager: AgentContextManager,
        error_mapper: AgentErrorMapper,
        feedback: AgentRunnerFeedback,
        context_publisher: AgentContextPublisher,
        event_publisher: AgentEventPublisher,
        tool_execution: AgentToolExecutor,
    ) -> None:
        self.agent_context_store = agent_context_store
        self.llm = llm
        self.tool_manager = tool_manager
        self.context_manager = context_manager
        self.error_mapper = error_mapper
        self.feedback = feedback
        self.context_publisher = context_publisher
        self.event_publisher = event_publisher
        self.tool_execution = tool_execution

    def execute(self, request: AgentRunnerRequest) -> AgentRunnerResult:
        state = self._build_runner_state(request)
        entry = self.context_publisher.publish_user_message(
            scope=state,
            text=state.config.task,
        )
        self.context_publisher.attach(entry)

        turn_loop = AgentLoop(max_turns=state.config.config.loop.max_turns)

        while turn_loop.has_next():
            self._append_last_turn_warning_if_needed(
                state=state,
                turn_loop=turn_loop,
            )
            context_request = self.context_manager.build_llm_request(state=state)
            turn_id = context_request.turn_id
            response = self.llm.generate(context_request.llm_request)
            if response.ok is False:
                state.fail_llm_request(
                    self.error_mapper.llm_request(
                        agent_id=state.agent_id,
                        response=response,
                    )
                )
                break
            state.record_llm_response(response)

            final_content = response.content
            has_invalid_final_content = (final_content is None 
                                         or not final_content.strip())

            if not state.tools_enabled and has_invalid_final_content:
                state.fail_invalid_final_message(
                    self.error_mapper.invalid_final_message(agent_id=state.agent_id)
                )
                break

            if not state.tools_enabled:
                assert final_content is not None
                final_text = final_content.strip()
                entry = self.context_publisher.publish_final_assistant_message(
                    scope=state,
                    turn_id=turn_id,
                    text=final_text,
                    usage=response.usage,
                )
                self.event_publisher.emit_assistant_message(entry=entry)
                state.finish_final(final_text)
                turn_loop.advance()
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
            if state.finish == AgentRunnerFinish.FINAL and has_invalid_final_content:
                state.fail_invalid_final_message(
                    self.error_mapper.invalid_final_message(agent_id=state.agent_id)
                )
                break

            if state.finish == AgentRunnerFinish.FINAL:
                assert final_content is not None
                final_text = final_content.strip()
                entry = self.context_publisher.publish_final_assistant_message(
                    scope=state,
                    turn_id=turn_id,
                    text=final_text,
                    usage=response.usage,
                )
                self.event_publisher.emit_assistant_message(entry=entry)
                state.finish_final(final_text)
                break
            if state.finish == AgentRunnerFinish.INTERRUPTED:
                self.event_publisher.emit_interrupted(
                    run_id=state.run_id,
                    step_id=state.agent_id,
                    turn_id=turn_id,
                )
                break
            break

        if state.finish is None:
            turn_id = self.agent_context_store.next_turn_id(scope=state)
            self.context_publisher.publish_user_message(
                scope=state,
                text=self.feedback.max_turns_exhausted(),
            )
            state.finish_max_turns_exhausted()
            self.event_publisher.emit_max_turns_exhausted(
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
            allowed_tools=list(state.config.tools),
            max_tool_calls=state.config.config.loop.max_tool_calls,
            turn_loop=turn_loop,
        )

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
        self.context_publisher.publish_user_message(
            scope=state,
            text=warning,
        )

    def _get_enabled_tool_configs(
        self,
        *,
        agent_id: str,
        tools: tuple[str, ...],
    ) -> list[ToolConfig]:
        if not tools:
            return []
        return self.tool_manager.get_tool_configs(list(tools))
