from __future__ import annotations

from skiller.application.agent.agent_runner import AgentRunner
from skiller.application.agent.config.event_output_sanitizer import (
    AgentEventOutputSanitizer,
)
from skiller.application.agent.observer.runtime_event_emitter import AgentRuntimeEventEmitter
from skiller.application.agent.prompt.final_message_extractor import (
    AgentFinalMessageExtractor,
)
from skiller.application.agent.prompt.prompt_builder import AgentPromptBuilder
from skiller.application.agent.tools.tool_manager import ToolManager
from skiller.application.agent.tools.tool_turn_executor import AgentToolTurnExecutor
from skiller.application.ports.agent.agent_context_store_port import AgentContextStorePort
from skiller.application.ports.agent.agent_steering_port import AgentSteeringPort
from skiller.application.ports.llm.llm_port import LLMPort
from skiller.application.use_cases.run.append_runtime_event import AppendRuntimeEventUseCase


class _NullAgentSteering(AgentSteeringPort):
    def enqueue(self, run_id: str, item) -> None:  # noqa: ANN001
        return None

    def consume_abort_turn(self, run_id: str) -> bool:
        return False

    def pop_steering_messages(self, run_id: str) -> list[str]:
        return []


def build_agent_tool_turn_executor(
    *,
    agent_context_store: AgentContextStorePort,
    agent_steering: AgentSteeringPort | None = None,
    tool_manager: ToolManager | None,
    append_runtime_event_use_case: AppendRuntimeEventUseCase | None = None,
    event_output_sanitizer: AgentEventOutputSanitizer | None = None,
) -> AgentToolTurnExecutor:
    return AgentToolTurnExecutor(
        agent_context_store=agent_context_store,
        agent_steering=agent_steering or _NullAgentSteering(),
        tool_manager=tool_manager,
        event_output_sanitizer=event_output_sanitizer or AgentEventOutputSanitizer(),
        event_emitter=AgentRuntimeEventEmitter(
            append_runtime_event_use_case=append_runtime_event_use_case
        ),
    )


def build_agent_runner(
    *,
    agent_context_store: AgentContextStorePort,
    agent_steering: AgentSteeringPort | None = None,
    llm: LLMPort,
    tool_manager: ToolManager | None,
    append_runtime_event_use_case: AppendRuntimeEventUseCase | None = None,
    event_output_sanitizer: AgentEventOutputSanitizer | None = None,
) -> AgentRunner:
    return AgentRunner(
        agent_context_store=agent_context_store,
        agent_steering=agent_steering or _NullAgentSteering(),
        llm=llm,
        tool_manager=tool_manager,
        prompt_builder=AgentPromptBuilder(),
        final_message_extractor=AgentFinalMessageExtractor(),
        event_output_sanitizer=event_output_sanitizer or AgentEventOutputSanitizer(),
        event_emitter=AgentRuntimeEventEmitter(
            append_runtime_event_use_case=append_runtime_event_use_case
        ),
        tool_turn_executor=build_agent_tool_turn_executor(
            agent_context_store=agent_context_store,
            agent_steering=agent_steering,
            tool_manager=tool_manager,
            append_runtime_event_use_case=append_runtime_event_use_case,
            event_output_sanitizer=event_output_sanitizer,
        ),
    )
