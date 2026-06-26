from dataclasses import dataclass

from skiller.application.agent.config.step_config_reader import AgentRunnerConfig
from skiller.application.agent.prompt.prompt_builder import AgentPromptBuilder
from skiller.domain.agent.context.model import (
    AgentContextEntry,
)
from skiller.domain.agent.context.store_port import AgentContextStorePort
from skiller.domain.agent.llm.request import LLMRequest
from skiller.domain.agent.run.identity import AgentContext
from skiller.domain.run.run_agent_store_port import RunAgentStorePort
from skiller.domain.run.run_model import RunAgentWindow


@dataclass(frozen=True)
class AgentContextLLMRequest:
    context_id: str
    turn_id: str
    llm_request: LLMRequest
    window_width_tokens: int
    window_start_sequence: int
    window_end_sequence: int
    max_ratio: float
    estimated_tokens: int


class AgentContextManager:
    def __init__(
        self,
        *,
        agent_context_store: AgentContextStorePort,
        run_agent_store: RunAgentStorePort,
        prompt_builder: AgentPromptBuilder,
    ) -> None:
        self.agent_context_store = agent_context_store
        self.run_agent_store = run_agent_store
        self.prompt_builder = prompt_builder

    def build_window_context(
        self,
        *,
        context: AgentContext,
        config: AgentRunnerConfig,
    ) -> AgentContextLLMRequest:
        provider = config.config.llm.default()
        max_ratio = config.config.context.compaction.max_total_tokens_ratio
        window_width_tokens = provider.context_max_tokens(ratio=max_ratio)
        entries = self.agent_context_store.list_window_entries(
            context_id=context.context_id,
            window_width_tokens=window_width_tokens,
        )
        window_start_sequence = _start_sequence(entries)
        run_agent = self.run_agent_store.get_agent(
            run_id=context.run_id,
            agent_id=context.agent_id,
        )
        window_base = (
            run_agent is None
            or run_agent.window_start_sequence != window_start_sequence
        )
        self.run_agent_store.update_agent_window(
            run_id=context.run_id,
            window=RunAgentWindow(
                agent_id=context.agent_id,
                window_start_sequence=window_start_sequence,
                window_base=window_base,
            ),
        )
        turn_id = self.agent_context_store.next_turn_id(context_id=context.context_id)
        llm_request = self.prompt_builder.build_request(
            provider=provider,
            system=config.system,
            entries=entries,
            tools=config.tools,
        )
        return AgentContextLLMRequest(
            context_id=context.context_id,
            turn_id=turn_id,
            llm_request=llm_request,
            window_width_tokens=window_width_tokens,
            window_start_sequence=window_start_sequence,
            window_end_sequence=_end_sequence(entries),
            max_ratio=max_ratio,
            estimated_tokens=_estimated_tokens(entries),
        )


def _estimated_tokens(entries: list[AgentContextEntry]) -> int:
    return sum(entry.delta_tokens or 0 for entry in entries)


def _start_sequence(entries: list[AgentContextEntry]) -> int:
    if not entries:
        return 0
    return entries[0].sequence


def _end_sequence(entries: list[AgentContextEntry]) -> int:
    if not entries:
        return 0
    return entries[-1].sequence
