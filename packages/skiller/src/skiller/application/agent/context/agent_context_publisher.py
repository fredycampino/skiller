from skiller.application.agent.mapper.feedback import AgentRunnerFeedback
from skiller.domain.agent.agent_context_model import AgentContextEntry
from skiller.domain.agent.agent_context_store_port import AgentContextStorePort
from skiller.domain.agent.agent_run_scope import AgentRunScope
from skiller.domain.agent.llm_model import LLMToolCall, LLMUsage
from skiller.domain.run.run_store_port import RunStorePort
from skiller.domain.tool.tool_execution_model import (
    AgentToolCall,
    AgentToolResult,
    ToolExecutionRequest,
)


class AgentContextPublisher:
    def __init__(
        self,
        agent_context_store: AgentContextStorePort,
        run_store: RunStorePort,
        feedback: AgentRunnerFeedback,
    ) -> None:
        self.agent_context_store = agent_context_store
        self.run_store = run_store
        self.feedback = feedback
        self._attached_agents: dict[tuple[str, str], str] = {}

    def attach(self, entry: AgentContextEntry) -> None:
        cache_key = (entry.run_id, entry.source_step_id)
        if self._attached_agents.get(cache_key) == entry.context_id:
            return

        agent = self.run_store.get_agent(
            run_id=entry.run_id,
            agent_id=entry.source_step_id,
        )
        if agent is not None and agent.context_id:
            self._attached_agents[cache_key] = agent.context_id
            return

        self.run_store.attach_agent(
            run_id=entry.run_id,
            agent_id=entry.source_step_id,
            context_id=entry.context_id,
        )
        self._attached_agents[cache_key] = entry.context_id

    def publish_user_message(
        self,
        *,
        scope: AgentRunScope,
        text: str,
    ) -> AgentContextEntry:
        return self.agent_context_store.append_user_message(
            scope=scope,
            text=text,
        )

    def publish_final_assistant_message(
        self,
        *,
        scope: AgentRunScope,
        turn_id: str,
        text: str,
        usage: LLMUsage | None = None,
    ) -> AgentContextEntry:
        return self._publish_assistant_message(
            scope=scope,
            turn_id=turn_id,
            message_type="final",
            text=text,
            usage=usage,
        )

    def publish_assistant_message(
        self,
        *,
        scope: AgentRunScope,
        turn_id: str,
        message_type: str,
        text: str,
        usage: LLMUsage | None = None,
    ) -> AgentContextEntry:
        return self._publish_assistant_message(
            scope=scope,
            turn_id=turn_id,
            message_type=message_type,
            text=text,
            usage=usage,
        )

    def publish_tool_call(
        self,
        *,
        request: ToolExecutionRequest,
        tool_call: AgentToolCall,
    ) -> AgentContextEntry:
        return self.agent_context_store.append_tool_call(
            scope=request,
            tool_call=tool_call,
        )

    def publish_tool_result(
        self,
        *,
        request: ToolExecutionRequest,
        tool_result: AgentToolResult,
    ) -> AgentContextEntry:
        return self.agent_context_store.append_tool_result(
            scope=request,
            tool_result=tool_result,
        )

    def publish_tool_limit_feedback(
        self,
        *,
        request: ToolExecutionRequest,
        tool_call_count: int,
    ) -> AgentContextEntry:
        return self.agent_context_store.append_user_message(
            scope=request,
            text=self.feedback.too_many_tool_calls(
                step_id=request.step_id,
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
            scope=request,
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
            scope=request,
            text=self.feedback.invalid_tool_call_arguments(
                step_id=request.step_id,
                tool_call=tool_call,
                error=error,
            ),
        )

    def _publish_assistant_message(
        self,
        *,
        scope: AgentRunScope,
        turn_id: str,
        message_type: str,
        text: str,
        usage: LLMUsage | None = None,
    ) -> AgentContextEntry:
        return self.agent_context_store.append_assistant_message(
            scope=scope,
            turn_id=turn_id,
            message_type=message_type,
            text=text,
            usage=usage,
        )
