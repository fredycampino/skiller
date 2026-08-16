from dataclasses import dataclass

from skiller.application.agent.config.step_config_reader import AgentRunnerConfig
from skiller.application.agent.prompt.prompt_builder import AgentPromptBuilder
from skiller.domain.agent.context.compact_delta import estimate_delta_tokens_from_chars
from skiller.domain.agent.context.context_state_port import AgentContextStatePort
from skiller.domain.agent.context.context_store_port import AgentContextStorePort
from skiller.domain.agent.context.model import (
    AgentContextCompactionQuery,
    AgentContextEntry,
    AgentContextState,
    AgentContextWindowEntries,
    AgentContextWindowQuery,
)
from skiller.domain.agent.llm.request import LLMRequest
from skiller.domain.agent.run.identity import AgentContext


@dataclass(frozen=True)
class AgentContextLLMRequest:
    context_id: str
    turn_id: str
    llm_request: LLMRequest
    window_width_tokens: int
    window_end_sequence: int
    max_ratio: float
    estimated_tokens: int


class AgentContextManager:
    def __init__(
        self,
        *,
        agent_context_store: AgentContextStorePort,
        agent_context_state: AgentContextStatePort,
        prompt_builder: AgentPromptBuilder,
    ) -> None:
        self.agent_context_store = agent_context_store
        self.agent_context_state = agent_context_state
        self.prompt_builder = prompt_builder

    def build_context(
        self,
        *,
        context: AgentContext,
        config: AgentRunnerConfig,
    ) -> AgentContextLLMRequest:
        provider = config.provider_definition
        model = config.model_definition()
        context_config = config.config.context
        model_context_window_tokens = model.context_window_tokens
        window_tokens = context_config.effective_context_tokens(
            model_context_window_tokens=model_context_window_tokens,
        )
        trigger_tokens = context_config.compaction_trigger_tokens(
            model_context_window_tokens=model_context_window_tokens,
        )
        target_tokens = context_config.compaction_target_tokens(
            model_context_window_tokens=model_context_window_tokens,
        )
        state = self.agent_context_state.get_state(context_id=context.context_id)

        context_window = self._recover_context_window(state=state)
        system_tokens = estimate_delta_tokens_from_chars(
            block_chars=len(config.system),
        )
        estimated_request_tokens = context_window.estimated_tokens + system_tokens
        if estimated_request_tokens >= trigger_tokens:
            compaction = context_config.compaction
            query = AgentContextCompactionQuery(
                context_id=state.context_id,
                start_sequence=state.start_sequence,
                compacted_sequence=state.compacted_sequence,
                compaction_id=state.compaction_id,
                keep_last_blocks=compaction.keep_last_blocks,
                target_tokens=target_tokens,
            )
            state = self.agent_context_store.select_compaction_state(query=query)
            self.agent_context_state.save_state(state=state)
            context_window = self._recover_context_window(state=state)

        entries = context_window.entries
        turn_id = self.agent_context_store.next_turn_id(context_id=context.context_id)
        log_request_file = None
        if config.config.debug.log_request:
            log_request_file = config.config.debug.log_request_file
        llm_request = self.prompt_builder.build_request(
            provider=provider,
            model=model,
            system=config.system,
            entries=entries,
            tools=config.tools,
            context_id=context.context_id,
            log_request_file=log_request_file,
            log_override_file=config.config.debug.log_override_file,
        )
        return AgentContextLLMRequest(
            context_id=context.context_id,
            turn_id=turn_id,
            llm_request=llm_request,
            window_width_tokens=window_tokens,
            window_end_sequence=_end_sequence(entries),
            max_ratio=context_config.compaction.compaction_trigger_ratio,
            estimated_tokens=context_window.estimated_tokens,
        )

    def _recover_context_window(
        self,
        *,
        state: AgentContextState,
    ) -> AgentContextWindowEntries:
        query = AgentContextWindowQuery(
            context_id=state.context_id,
            start_sequence=state.start_sequence,
            compacted_sequence=state.compacted_sequence,
        )
        compacted = self.agent_context_store.list_compact_entries(query=query)
        raw = self.agent_context_store.list_raw_entries(query=query)
        entries = compacted.entries + raw.entries
        estimated_tokens = compacted.estimated_tokens + raw.estimated_tokens
        return AgentContextWindowEntries(
            entries=entries,
            estimated_tokens=estimated_tokens,
        )


def _end_sequence(entries: list[AgentContextEntry]) -> int:
    if not entries:
        return 0
    return entries[-1].sequence
