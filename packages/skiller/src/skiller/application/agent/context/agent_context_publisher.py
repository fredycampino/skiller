from uuid import uuid4

from skiller.application.agent.context.agent_context_marker_calculator import (
    AgentContextMarkerCalculator,
)
from skiller.application.agent.mapper.feedback import AgentRunnerFeedback
from skiller.domain.agent.context.context_store_port import AgentContextStorePort
from skiller.domain.agent.context.model import (
    AgentAssistantMessagePayload,
    AgentAssistantMessageType,
    AgentContextEntry,
)
from skiller.domain.agent.llm.model import LLMToolCall, LLMUsage
from skiller.domain.agent.run.identity import AgentContext, AgentRun
from skiller.domain.run.run_agent_store_port import RunAgentStorePort
from skiller.domain.tool.tool_execution_model import (
    AgentToolCall,
    AgentToolResult,
    ToolExecutionRequest,
)


class AgentContextPublisher:
    def __init__(
        self,
        agent_context_store: AgentContextStorePort,
        run_agent_store: RunAgentStorePort,
        marker_calculator: AgentContextMarkerCalculator,
        feedback: AgentRunnerFeedback,
    ) -> None:
        self.agent_context_store = agent_context_store
        self.run_agent_store = run_agent_store
        self.marker_calculator = marker_calculator
        self.feedback = feedback
        self._attached_contexts: dict[AgentRun, AgentContext] = {}

    def attach_context(
        self,
        *,
        agent: AgentRun,
    ) -> AgentContext:
        cached_context = self._attached_contexts.get(agent)
        if cached_context is not None:
            return cached_context

        run_agent = self.run_agent_store.get_agent(
            run_id=agent.run_id,
            agent_id=agent.agent_id,
        )
        if run_agent is not None and run_agent.context_id:
            context = AgentContext(
                run_id=agent.run_id,
                agent_id=agent.agent_id,
                context_id=run_agent.context_id,
            )
            self._attached_contexts[agent] = context
            return context

        context_uuid = uuid4()
        context_id = str(context_uuid)

        self.run_agent_store.attach_agent(
            run_id=agent.run_id,
            agent_id=agent.agent_id,
            context_id=context_id,
        )
        context = AgentContext(
            run_id=agent.run_id,
            agent_id=agent.agent_id,
            context_id=context_id,
        )
        self._attached_contexts[agent] = context
        return context

    def publish_user_message(
        self,
        *,
        context: AgentContext,
        text: str,
    ) -> AgentContextEntry:
        return self.agent_context_store.append_user_message(
            context=context,
            text=text,
        )

    def publish_last_turn_warning(
        self,
        *,
        context: AgentContext,
    ) -> AgentContextEntry:
        return self.publish_user_message(
            context=context,
            text=self.feedback.last_turn_warning(),
        )

    def publish_final_assistant_message(
        self,
        *,
        context: AgentContext,
        turn_id: str,
        text: str,
        usage: LLMUsage | None,
    ) -> AgentContextEntry:
        payload = AgentAssistantMessagePayload(
            turn_id=turn_id,
            message_type=AgentAssistantMessageType.FINAL,
            text=text,
        )
        marker = self.marker_calculator.calculate(
            context=context,
            usage=usage,
            payload=payload,
        )
        entry = self.agent_context_store.append_final_assistant_message(
            context=context,
            turn_id=turn_id,
            text=text,
            usage=usage,
            delta_tokens=marker.delta_tokens,
            compaction_id=marker.compaction_id,
        )
        if marker.compaction_id is not None:
            self.agent_context_store.add_compact_delta_tokens(
                context_id=entry.context_id,
                marker_sequence=entry.sequence,
            )
        return entry

    def publish_tool_calls_assistant_message(
        self,
        *,
        context: AgentContext,
        turn_id: str,
        text: str,
        usage: LLMUsage | None = None,
    ) -> AgentContextEntry:
        payload = AgentAssistantMessagePayload(
            turn_id=turn_id,
            message_type=AgentAssistantMessageType.TOOL_CALLS,
            text=text,
        )
        marker = self.marker_calculator.calculate(
            context=context,
            usage=usage,
            payload=payload,
        )
        entry = self.agent_context_store.append_tool_calls_assistant_message(
            context=context,
            turn_id=turn_id,
            text=text,
            usage=usage,
            delta_tokens=marker.delta_tokens,
            compaction_id=marker.compaction_id,
        )
        if marker.compaction_id is not None:
            self.agent_context_store.add_compact_delta_tokens(
                context_id=entry.context_id,
                marker_sequence=entry.sequence,
            )
        return entry

    def publish_tool_call(
        self,
        *,
        request: ToolExecutionRequest,
        tool_call: AgentToolCall,
    ) -> AgentContextEntry:
        return self.agent_context_store.append_tool_call(
            context=request.context,
            tool_call=tool_call,
        )

    def publish_tool_result(
        self,
        *,
        request: ToolExecutionRequest,
        tool_result: AgentToolResult,
    ) -> AgentContextEntry:
        return self.agent_context_store.append_tool_result(
            context=request.context,
            tool_result=tool_result,
        )

    def publish_tool_limit_feedback(
        self,
        *,
        request: ToolExecutionRequest,
        tool_call_count: int,
    ) -> AgentContextEntry:
        return self.agent_context_store.append_user_message(
            context=request.context,
            text=self.feedback.too_many_tool_calls(
                step_id=request.context.agent_id,
                max_tool_calls=request.max_tool_calls,
                tool_call_count=tool_call_count,
            ),
        )

    def publish_interrupt_feedback(
        self,
        *,
        request: ToolExecutionRequest,
    ) -> AgentContextEntry:
        return self.agent_context_store.append_user_message(
            context=request.context,
            text=self.feedback.user_interrupted_turn(),
        )

    def publish_invalid_tool_call(
        self,
        *,
        request: ToolExecutionRequest,
        tool_call: LLMToolCall,
        error: ValueError,
    ) -> AgentContextEntry:
        return self.agent_context_store.append_user_message(
            context=request.context,
            text=self.feedback.invalid_tool_call_arguments(
                step_id=request.context.agent_id,
                tool_call=tool_call,
                error=error,
            ),
        )
