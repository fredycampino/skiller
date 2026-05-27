from __future__ import annotations

from skiller.application.agent.context.agent_context_manager import AgentContextManager
from skiller.application.agent.context.agent_context_publisher import (
    AgentContextPublisher,
)
from skiller.application.agent.event.agent_event_publisher import AgentEventPublisher
from skiller.application.agent.llmodel.llm_model_manager import LLMModelManager
from skiller.application.agent.mapper.error_mapper import AgentErrorMapper
from skiller.application.agent.mapper.feedback import AgentRunnerFeedback
from skiller.application.agent.runner_state import (
    AgentRunnerRequest,
    AgentRunnerResult,
    AgentRunnerState,
)
from skiller.application.agent.tools.agent_tool_executor import AgentToolExecutor
from skiller.domain.agent.agent_context_store_port import AgentContextStorePort
from skiller.domain.agent.agent_loop_model import AgentLoop
from skiller.domain.agent.agent_run_model import AgentRunnerFinish
from skiller.domain.tool.tool_execution_model import (
    ToolExecutionRequest,
)


class AgentRunner:
    def __init__(
        self,
        *,
        agent_context_store: AgentContextStorePort,
        llm_model: LLMModelManager,
        context_manager: AgentContextManager,
        error_mapper: AgentErrorMapper,
        feedback: AgentRunnerFeedback,
        context_publisher: AgentContextPublisher,
        event_publisher: AgentEventPublisher,
        tool_execution: AgentToolExecutor,
    ) -> None:
        self.agent_context_store = agent_context_store
        self.llm_model = llm_model
        self.context_manager = context_manager
        self.error_mapper = error_mapper
        self.feedback = feedback
        self.context_publisher = context_publisher
        self.event_publisher = event_publisher
        self.tool_execution = tool_execution

    def execute(self, request: AgentRunnerRequest) -> AgentRunnerResult:
        config = request.config
        tools_enabled = bool(config.tools)
        context = self.context_publisher.attach_context(
            agent=request.agent,
        )
        self.context_publisher.publish_user_message(
            context=context,
            text=config.task,
        )
        
        state = AgentRunnerState()
        turn_loop = AgentLoop(max_turns=config.config.loop.max_turns)

        while turn_loop.has_next():
            if tools_enabled and turn_loop.is_last_turn():
                self.context_publisher.publish_last_turn_warning(
                    context=context,
                )

            context_request = self.context_manager.build_window_context(
                context=context,
                config=config,
            )
            turn_id = context_request.turn_id
            response = self.llm_model.generate(
                provider=config.config.llm.default(),
                request=context_request.llm_request,
            )
            if response.ok is False:
                state.fail_llm_request(
                    self.error_mapper.llm_request(
                        agent_id=context.agent_id,
                        response=response,
                    )
                )
                break
            state.record_llm_response(response)

            final_content = response.content
            has_invalid_final_content = (
                final_content is None
                or not final_content.strip()
            )

            if not tools_enabled and has_invalid_final_content:
                error = self.error_mapper.invalid_final_message(
                    agent_id=context.agent_id,
                )
                state.fail_invalid_final_message(error)
                break

            if not tools_enabled:
                assert final_content is not None
                final_text = final_content.strip()
                entry = self.context_publisher.publish_final_assistant_message(
                    context=context,
                    turn_id=turn_id,
                    text=final_text,
                    usage=response.usage,
                )
                self.event_publisher.emit_final_assistant_message(
                    entry=entry,
                    config=config.config.event_output,
                )
                state.finish_final(final_text)
                turn_loop.advance()
                break

            allowed_tools = [tool.name for tool in config.tools]
            max_tool_calls = config.config.loop.max_tool_calls
            tool_execution_request = ToolExecutionRequest(
                context=context,
                turn_id=turn_id,
                response=response,
                allowed_tools=allowed_tools,
                runtime_configs=config.config.tools,
                event_config=config.config.event_output,
                max_tool_calls=max_tool_calls,
                turn_loop=turn_loop,
            )
            tool_execution_results = self.tool_execution.execute(tool_execution_request)
            turn_loop.advance()
            state.record_tool_execution(tool_execution_results)
            if state.finish is None:
                continue
            if state.finish == AgentRunnerFinish.FINAL and has_invalid_final_content:
                error = self.error_mapper.invalid_final_message(
                    agent_id=context.agent_id,
                )
                state.fail_invalid_final_message(error)
                break

            if state.finish == AgentRunnerFinish.FINAL:
                assert final_content is not None
                final_text = final_content.strip()
                entry = self.context_publisher.publish_final_assistant_message(
                    context=context,
                    turn_id=turn_id,
                    text=final_text,
                    usage=response.usage,
                )
                self.event_publisher.emit_final_assistant_message(
                    entry=entry,
                    config=config.config.event_output,
                )
                state.finish_final(final_text)
                break
            if state.finish == AgentRunnerFinish.INTERRUPTED:
                self.event_publisher.emit_interrupted(
                    run_id=context.run_id,
                    step_id=context.agent_id,
                    turn_id=turn_id,
                )
                break
            break

        if state.finish is None:
            turn_id = self.agent_context_store.next_turn_id(
                context_id=context.context_id,
            )
            self.context_publisher.publish_user_message(
                context=context,
                text=self.feedback.max_turns_exhausted(),
            )
            state.finish_max_turns_exhausted()
            self.event_publisher.emit_max_turns_exhausted(
                run_id=context.run_id,
                step_id=context.agent_id,
                turn_id=turn_id,
            )

        return AgentRunnerResult(
            context_id=context.context_id,
            final_text=state.final_text,
            turn_count=turn_loop.turn_count,
            tool_call_count=state.tool_call_count,
            finish=state.finish or AgentRunnerFinish.FINAL,
            response_model=state.response_model,
            usage=state.usage,
            error=state.error,
        )
