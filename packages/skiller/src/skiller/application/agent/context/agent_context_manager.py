from dataclasses import dataclass

from skiller.application.agent.config.step_config_reader import AgentRunnerConfig
from skiller.application.agent.prompt.prompt_builder import AgentPromptBuilder
from skiller.domain.agent.agent_context_model import (
    AgentAssistantMessageType,
    AgentContextEntry,
    AgentContextEntryType,
)
from skiller.domain.agent.agent_context_store_port import AgentContextStorePort
from skiller.domain.agent.agent_run_identity import AgentContext
from skiller.domain.agent.llm_model import LLMRequest


@dataclass(frozen=True)
class AgentContextLLMRequest:
    context_id: str
    turn_id: str
    llm_request: LLMRequest
    context_window_tokens: int
    window_start_sequence: int
    window_end_sequence: int
    max_ratio: float
    estimated_tokens: int


class AgentContextManager:
    def __init__(
        self,
        *,
        agent_context_store: AgentContextStorePort,
        prompt_builder: AgentPromptBuilder,
    ) -> None:
        self.agent_context_store = agent_context_store
        self.prompt_builder = prompt_builder

    def build_window_context(
        self,
        *,
        context: AgentContext,
        config: AgentRunnerConfig,
    ) -> AgentContextLLMRequest:
        provider = config.config.llm.default()
        max_ratio = config.config.context.compaction.max_total_tokens_ratio
        context_window_tokens = int(
            provider.context_window_tokens * max_ratio,
        )
        context_window = self.agent_context_store.list_context_window(
            context_id=context.context_id,
            window_tokens=context_window_tokens,
        )
        entries = context_window.entries
        turn_id = self.agent_context_store.next_turn_id(context_id=context.context_id)
        llm_request = self.prompt_builder.build_request(
            model=provider.model,
            system=config.system,
            entries=entries,
            tools=config.tools,
        )
        return AgentContextLLMRequest(
            context_id=context.context_id,
            turn_id=turn_id,
            llm_request=llm_request,
            context_window_tokens=context_window_tokens,
            window_start_sequence=context_window.start_sequence,
            window_end_sequence=context_window.end_sequence,
            max_ratio=max_ratio,
            estimated_tokens=_estimated_tokens(entries),
        )


def _estimated_tokens(entries: list[AgentContextEntry]) -> int:
    if not entries:
        return 0

    last_total = _final_position_tokens(entries[-1])
    if last_total is None:
        return 0

    first_total = _final_position_tokens(entries[0])
    if first_total is None:
        return last_total
    return last_total - first_total


def _final_position_tokens(entry: AgentContextEntry) -> int | None:
    if entry.entry_type != AgentContextEntryType.ASSISTANT_MESSAGE:
        return None
    if entry.message_type != AgentAssistantMessageType.FINAL:
        return None
    return entry.position_tokens
