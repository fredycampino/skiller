from typing import Any

from skiller.application.use_cases.agent.get_agent_stats import (
    GetAgentStatsResult,
    GetAgentStatsStatus,
)
from skiller.application.use_cases.agent.interrupt_agent import (
    InterruptAgentResult,
    InterruptAgentStatus,
)
from skiller.domain.agent.agent_stats_model import AgentStats


class AgentServiceMapper:
    def to_interrupt_input(self, run_id: str) -> str:
        return run_id.strip()

    def to_interrupt_dict(self, result: InterruptAgentResult) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "run_id": result.run_id,
            "status": result.status.value,
            "enqueued": result.status == InterruptAgentStatus.ENQUEUED,
        }
        if result.item is not None:
            payload["item"] = result.item.to_dict()
        if result.error is not None:
            payload["error"] = result.error
        return payload

    def to_stats_input(self, run_id: str, agent_id: str) -> tuple[str, str]:
        return run_id.strip(), agent_id.strip()

    def to_stats_dict(self, result: GetAgentStatsResult) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "run_id": result.run_id,
            "agent_id": result.agent_id,
            "status": result.status.value,
            "ok": result.status == GetAgentStatsStatus.OK,
        }
        if result.stats is not None:
            payload["context_id"] = result.stats.context_id
            payload["stats"] = self._stats_to_dict(result.stats)
        if result.error is not None:
            payload["error"] = result.error
        return payload

    def _stats_to_dict(self, stats: AgentStats) -> dict[str, Any]:
        return {
            "context": {
                "entries": {
                    "total": stats.context.entries.total,
                    "user_messages": stats.context.entries.user_messages,
                    "assistant_messages": stats.context.entries.assistant_messages,
                    "tool_calls": stats.context.entries.tool_calls,
                    "tool_results": stats.context.entries.tool_results,
                },
                "usage": {
                    "entries": stats.context.usage.entries,
                    "total_prompt_tokens": stats.context.usage.total_prompt_tokens,
                    "total_response_tokens": stats.context.usage.total_response_tokens,
                    "total_tokens": stats.context.usage.total_tokens,
                },
            }
        }
