from skiller.domain.agent.context.context_state_port import AgentContextStatePort
from skiller.domain.agent.context.context_store_port import AgentContextStorePort
from skiller.domain.agent.context.model import (
    AgentContextMarker,
    AgentContextPayload,
)
from skiller.domain.agent.llm.model import LLMUsage
from skiller.domain.agent.run.identity import AgentContext


class AgentContextMarkerCalculator:
    def __init__(
        self,
        *,
        agent_context_store: AgentContextStorePort,
        agent_context_state: AgentContextStatePort,
    ) -> None:
        self.agent_context_store = agent_context_store
        self.agent_context_state = agent_context_state

    def calculate(
        self,
        *,
        context: AgentContext,
        usage: LLMUsage | None,
        payload: AgentContextPayload,
    ) -> AgentContextMarker:
        state = self.agent_context_state.get_state(context_id=context.context_id)
        prompt_tokens = usage.prompt_tokens if usage is not None else None
        last_marker = self.agent_context_store.get_last_usage_marker(
            context_id=context.context_id,
        )

        has_prompt_delta = (
            prompt_tokens is not None
            and last_marker is not None
            and last_marker.compaction_id == state.compaction_id
            and prompt_tokens >= last_marker.prompt_tokens
        )
        if has_prompt_delta:
            return AgentContextMarker(
                delta_tokens=prompt_tokens - last_marker.prompt_tokens,
                compaction_id=state.compaction_id,
            )

        last_marker_sequence = last_marker.sequence if last_marker is not None else 0
        delta_tokens = self.agent_context_store.estimate_delta_tokens(
            context_id=context.context_id,
            start_sequence=state.start_sequence,
            last_marker_sequence=last_marker_sequence,
            payload=payload,
        )
        return AgentContextMarker(
            delta_tokens=delta_tokens,
            compaction_id=(
                state.compaction_id
                if prompt_tokens is not None
                else None
            ),
        )
