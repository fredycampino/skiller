from dataclasses import dataclass
from uuid import uuid4

from skiller.application.agent.mapper.feedback import AgentRunnerFeedback
from skiller.domain.agent.context.compact_delta import compact_delta_tokens
from skiller.domain.agent.context.model import (
    AgentAssistantMessagePayload,
    AgentAssistantMessageType,
    AgentContextEntry,
    AgentContextPayload,
    AgentContextUsageMarker,
)
from skiller.domain.agent.context.store_port import AgentContextStorePort
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
        feedback: AgentRunnerFeedback,
    ) -> None:
        self.agent_context_store = agent_context_store
        self.run_agent_store = run_agent_store
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
        marker = self._response_marker(context=context, usage=usage, payload=payload)
        return self.agent_context_store.append_final_assistant_message(
            context=context,
            turn_id=turn_id,
            text=text,
            usage=usage,
            delta_tokens=marker.delta_tokens,
            delta_compact_tokens=marker.delta_compact_tokens,
            window_start_sequence=marker.window_start_sequence,
            window_base=marker.window_base,
        )

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
        marker = self._response_marker(context=context, usage=usage, payload=payload)
        return self.agent_context_store.append_tool_calls_assistant_message(
            context=context,
            turn_id=turn_id,
            text=text,
            usage=usage,
            delta_tokens=marker.delta_tokens,
            delta_compact_tokens=marker.delta_compact_tokens,
            window_start_sequence=marker.window_start_sequence,
            window_base=marker.window_base,
        )

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

    def _response_marker(
        self,
        *,
        context: AgentContext,
        usage: LLMUsage | None,
        payload: AgentContextPayload,
    ) -> "_ResponseMarker":
        run_agent = self.run_agent_store.get_agent(
            run_id=context.run_id,
            agent_id=context.agent_id,
        )
        window_start_sequence = (
            run_agent.window_start_sequence
            if run_agent is not None
            else 0
        )
        window_base = run_agent.window_base if run_agent is not None else True
        prompt_tokens = usage.prompt_tokens if usage is not None else None
        if prompt_tokens is None:
            return _ResponseMarker(
                delta_tokens=0,
                delta_compact_tokens=0,
                window_start_sequence=window_start_sequence,
                window_base=window_base,
            )

        last_marker = self.agent_context_store.get_last_usage_marker(
            context_id=context.context_id,
        )
        if last_marker is None:
            return self._build_response_marker(
                context=context,
                payload=payload,
                last_marker=last_marker,
                delta_tokens=prompt_tokens,
                window_start_sequence=window_start_sequence,
                window_base=True,
            )
        if last_marker.window_start_sequence != window_start_sequence or window_base:
            estimated_tokens = self.agent_context_store.estimate_window_tokens(
                context_id=context.context_id,
                start_sequence=window_start_sequence,
            )
            delta_tokens = prompt_tokens - estimated_tokens
            if delta_tokens < 0:
                delta_tokens = 0
            return self._build_response_marker(
                context=context,
                payload=payload,
                last_marker=last_marker,
                delta_tokens=delta_tokens,
                window_start_sequence=window_start_sequence,
                window_base=True,
            )
        if prompt_tokens < last_marker.prompt_tokens:
            return self._build_response_marker(
                context=context,
                payload=payload,
                last_marker=last_marker,
                delta_tokens=prompt_tokens,
                window_start_sequence=window_start_sequence,
                window_base=True,
            )
        return self._build_response_marker(
            context=context,
            payload=payload,
            last_marker=last_marker,
            delta_tokens=prompt_tokens - last_marker.prompt_tokens,
            window_start_sequence=window_start_sequence,
            window_base=False,
        )

    def _build_response_marker(
        self,
        *,
        context: AgentContext,
        payload: AgentContextPayload,
        last_marker: AgentContextUsageMarker | None,
        delta_tokens: int,
        window_start_sequence: int,
        window_base: bool,
    ) -> "_ResponseMarker":
        return _ResponseMarker(
            delta_tokens=delta_tokens,
            delta_compact_tokens=self._compact_delta_tokens(
                context=context,
                payload=payload,
                last_marker=last_marker,
                delta_tokens=delta_tokens,
            ),
            window_start_sequence=window_start_sequence,
            window_base=window_base,
        )

    def _compact_delta_tokens(
        self,
        *,
        context: AgentContext,
        payload: AgentContextPayload,
        last_marker: AgentContextUsageMarker | None,
        delta_tokens: int,
    ) -> int:
        payloads = self._compact_delta_payloads(
            context=context,
            payload=payload,
            last_marker=last_marker,
        )
        return compact_delta_tokens(
            delta_tokens=delta_tokens,
            payloads=payloads,
        )

    def _compact_delta_payloads(
        self,
        *,
        context: AgentContext,
        payload: AgentContextPayload,
        last_marker: AgentContextUsageMarker | None,
    ) -> list[AgentContextPayload]:
        if last_marker is None:
            return [payload]
        entries = self.agent_context_store.list_entries_from_sequence(
            context_id=context.context_id,
            start_sequence=last_marker.sequence,
        )
        return [entry.payload for entry in entries] + [payload]



@dataclass(frozen=True)
class _ResponseMarker:
    delta_tokens: int
    delta_compact_tokens: int
    window_start_sequence: int
    window_base: bool
