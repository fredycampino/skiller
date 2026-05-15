from skiller.application.agent.mapper.feedback import AgentRunnerFeedback
from skiller.domain.agent.agent_context_model import AgentContextEntry
from skiller.domain.agent.agent_context_store_port import AgentContextStorePort
from skiller.domain.agent.agent_run_scope import AgentRunScope
from skiller.domain.agent.llm_model import LLMToolCall
from skiller.domain.tool.tool_contract import ToolResult
from skiller.domain.tool.tool_execution_model import ToolExecutionRequest


class AgentContextPublisher:
    def __init__(
        self,
        agent_context_store: AgentContextStorePort,
        feedback: AgentRunnerFeedback,
    ) -> None:
        self.agent_context_store = agent_context_store
        self.feedback = feedback

    def publish_user_message(
        self,
        *,
        scope: AgentRunScope,
        turn_id: str,
        text: str,
    ) -> AgentContextEntry:
        return self.agent_context_store.append_user_message(
            scope=scope,
            turn_id=turn_id,
            text=text,
        )

    def publish_final_assistant_message(
        self,
        *,
        scope: AgentRunScope,
        turn_id: str,
        text: str,
    ) -> AgentContextEntry:
        return self._publish_assistant_message(
            scope=scope,
            turn_id=turn_id,
            message_type="final",
            text=text,
        )

    def publish_assistant_message(
        self,
        *,
        scope: AgentRunScope,
        turn_id: str,
        message_type: str,
        text: str,
    ) -> AgentContextEntry:
        return self._publish_assistant_message(
            scope=scope,
            turn_id=turn_id,
            message_type=message_type,
            text=text,
        )

    def publish_tool_call(
        self,
        *,
        request: ToolExecutionRequest,
        raw_tool_call: LLMToolCall,
        parent_sequence: int | None,
        parsed_args: dict[str, object],
    ) -> AgentContextEntry:
        return self.agent_context_store.append_tool_call(
            scope=request,
            turn_id=request.turn_id,
            parent_sequence=parent_sequence,
            tool_call_id=raw_tool_call.id,
            tool=str(raw_tool_call.function.name or "").strip() or "unknown",
            args=parsed_args,
        )

    def publish_tool_result(
        self,
        *,
        request: ToolExecutionRequest,
        tool_call: LLMToolCall,
        parent_sequence: int | None,
        result: ToolResult,
    ) -> AgentContextEntry:
        return self.agent_context_store.append_tool_result(
            scope=request,
            turn_id=request.turn_id,
            parent_sequence=parent_sequence,
            tool_call_id=tool_call.id,
            result=result,
        )

    def publish_tool_limit_feedback(
        self,
        *,
        request: ToolExecutionRequest,
        tool_call_count: int,
    ) -> AgentContextEntry:
        return self.agent_context_store.append_user_message(
            scope=request,
            turn_id=f"{request.turn_id}:tool-limit",
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
            turn_id=f"{request.turn_id}:interrupt",
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
            turn_id=f"{request.turn_id}:tool-format",
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
    ) -> AgentContextEntry:
        return self.agent_context_store.append_assistant_message(
            scope=scope,
            turn_id=turn_id,
            message_type=message_type,
            text=text,
        )
