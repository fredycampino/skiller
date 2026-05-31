from __future__ import annotations

import json

from pydantic import TypeAdapter, ValidationError

from stui.adapter.cli_agent_stats import CliAgentStats, CliAgentStatsFailure
from stui.port.agent_port import (
    AgentContextStats,
    AgentContextWindowStats,
    AgentStatsResult,
)

CLI_AGENT_STATS_ADAPTER = TypeAdapter(CliAgentStats)


class AgentStatsMapper:
    def map(self, raw: str) -> AgentStatsResult:
        payload = _load_json(raw)
        model = _validate_model(payload)
        if isinstance(model, CliAgentStatsFailure):
            return AgentStatsResult(
                status=model.status,
                run_id=model.run_id,
                agent_id=model.agent_id,
                error=model.error,
            )

        return AgentStatsResult(
            status=model.status,
            run_id=model.run_id,
            agent_id=model.agent_id,
            context_id=model.context_id,
            context=AgentContextStats(
                entries=model.context.entries,
                estimated_tokens=model.context.estimated_tokens,
                window=AgentContextWindowStats(
                    start_sequence=model.context.window.start_sequence,
                    end_sequence=model.context.window.end_sequence,
                    current_tokens=model.context.window.current_tokens,
                    limit_tokens=model.context.window.limit_tokens,
                    capacity_tokens=model.context.window.capacity_tokens,
                ),
            ),
        )


def _load_json(raw: str) -> object:
    if not isinstance(raw, str):
        raise RuntimeError("agent stats command returned invalid JSON")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("agent stats command returned invalid JSON") from exc


def _validate_model(payload: object) -> CliAgentStats:
    try:
        return CLI_AGENT_STATS_ADAPTER.validate_python(payload)
    except ValidationError as exc:
        raise RuntimeError(f"agent stats command returned invalid payload: {exc}") from exc
