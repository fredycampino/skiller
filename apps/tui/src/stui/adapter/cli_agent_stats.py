from __future__ import annotations

from typing import Literal, TypeAlias

from pydantic import BaseModel, ConfigDict

from stui.port.agent_port import AgentStatsStatus


class CliAgentContextWindowStats(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_sequence: int
    end_sequence: int
    current_tokens: int
    limit_tokens: int
    capacity_tokens: int


class CliAgentContextStats(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entries: int
    estimated_tokens: int
    window: CliAgentContextWindowStats


class CliAgentStatsOk(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    agent_id: str
    status: Literal[AgentStatsStatus.OK]
    ok: Literal[True]
    context_id: str
    context: CliAgentContextStats


class CliAgentStatsFailure(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    agent_id: str
    status: Literal[
        AgentStatsStatus.RUN_NOT_FOUND,
        AgentStatsStatus.AGENT_NOT_FOUND,
        AgentStatsStatus.AGENT_CONTEXT_NOT_READY,
    ]
    ok: Literal[False]
    error: str


CliAgentStats: TypeAlias = CliAgentStatsOk | CliAgentStatsFailure
