from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from stui.port.run_port import CommandAck


class AgentStatsStatus(StrEnum):
    OK = "OK"
    RUN_NOT_FOUND = "RUN_NOT_FOUND"
    AGENT_NOT_FOUND = "AGENT_NOT_FOUND"
    AGENT_CONTEXT_NOT_READY = "AGENT_CONTEXT_NOT_READY"
    ERROR = "ERROR"


@dataclass(frozen=True)
class AgentContextWindowStats:
    start_sequence: int
    end_sequence: int
    current_tokens: int
    limit_tokens: int
    capacity_tokens: int


@dataclass(frozen=True)
class AgentContextStats:
    entries: int
    estimated_tokens: int
    window: AgentContextWindowStats


@dataclass(frozen=True)
class AgentStatsResult:
    status: AgentStatsStatus
    run_id: str
    agent_id: str
    context_id: str = ""
    context: AgentContextStats | None = None
    error: str = ""


class AgentPort(Protocol):
    def interrupt(self, run_id: str) -> CommandAck: ...

    def stats(self, *, run_id: str, agent_id: str) -> AgentStatsResult: ...
