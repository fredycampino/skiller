import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from skiller.domain.agent.config.port import AgentConfigPort
from skiller.domain.agent.context.context_store_port import AgentContextStorePort
from skiller.domain.agent.context.model import (
    AgentAssistantMessageType,
    AgentContextEntry,
    AgentContextEntryType,
    agent_context_payload_to_dict,
)
from skiller.domain.run.run_agent_store_port import RunAgentStorePort
from skiller.domain.run.run_store_port import RunStorePort
from skiller.domain.step.runner_port import RunnerPort


class ListAgentContextStatus(str, Enum):
    OK = "OK"
    RUN_NOT_FOUND = "RUN_NOT_FOUND"
    AGENT_NOT_FOUND = "AGENT_NOT_FOUND"
    AGENT_CONTEXT_NOT_READY = "AGENT_CONTEXT_NOT_READY"


@dataclass(frozen=True)
class AgentContextWindow:
    mode: str
    entries: int
    start_sequence: int
    end_sequence: int
    limit_tokens: int
    estimated_tokens: int
    payload_bytes: int
    keep_last: int


@dataclass(frozen=True)
class AgentContextEntryItem:
    sequence: int
    role: str
    type: str
    delta_tokens: int | None
    delta_compact_tokens: int | None
    payload_bytes: int
    usage: bool
    prunable: bool
    window_start_sequence: int | None
    window_base: bool | None


@dataclass(frozen=True)
class ListAgentContextResult:
    status: ListAgentContextStatus
    run_id: str
    agent_id: str
    context_id: str | None = None
    window: AgentContextWindow | None = None
    entries: tuple[AgentContextEntryItem, ...] = ()
    error: str | None = None


class ListAgentContextUseCase:
    def __init__(
        self,
        *,
        run_store: RunStorePort,
        run_agent_store: RunAgentStorePort,
        agent_context_store: AgentContextStorePort,
        agent_config: AgentConfigPort,
        skill_runner: RunnerPort,
    ) -> None:
        self.run_store = run_store
        self.run_agent_store = run_agent_store
        self.agent_context_store = agent_context_store
        self.agent_config = agent_config
        self.skill_runner = skill_runner

    def execute(self, run_id: str, agent_id: str) -> ListAgentContextResult:
        if not run_id or not agent_id:
            raise RuntimeError("ListAgentContextUseCase requires run_id and agent_id")

        run = self.run_store.get_run(run_id)
        if run is None:
            return ListAgentContextResult(
                status=ListAgentContextStatus.RUN_NOT_FOUND,
                run_id=run_id,
                agent_id=agent_id,
                error=f"Run '{run_id}' not found",
            )

        agent = self.run_agent_store.get_agent(run_id=run_id, agent_id=agent_id)
        if agent is None:
            return ListAgentContextResult(
                status=ListAgentContextStatus.AGENT_NOT_FOUND,
                run_id=run_id,
                agent_id=agent_id,
                error=f"Agent '{agent_id}' not found in run '{run_id}'",
            )
        if not agent.context_id:
            return ListAgentContextResult(
                status=ListAgentContextStatus.AGENT_CONTEXT_NOT_READY,
                run_id=run_id,
                agent_id=agent_id,
                error=f"Agent '{agent_id}' has no attached context in run '{run_id}'",
            )

        config_path = self._resolve_agent_config_path(run.source, run.ref)
        config = self.agent_config.get_config(config_path=config_path)
        provider = config.llm.default()
        compaction = config.context.compaction
        limit_tokens = provider.context_max_tokens(ratio=compaction.max_total_tokens_ratio)
        if compaction.enabled:
            mode = "compact"
            context_window = self.agent_context_store.list_compact_entries(
                context_id=agent.context_id,
                window_width_tokens=limit_tokens,
                keep_last_blocks=compaction.keep_last,
            )
        else:
            mode = "window"
            context_window = self.agent_context_store.list_window_entries(
                context_id=agent.context_id,
                window_width_tokens=limit_tokens,
            )

        entries = context_window.entries
        items = tuple(_to_context_item(entry) for entry in entries)
        payload_bytes = sum(item.payload_bytes for item in items)
        window = AgentContextWindow(
            mode=mode,
            entries=len(items),
            start_sequence=_start_sequence(entries),
            end_sequence=_end_sequence(entries),
            limit_tokens=limit_tokens,
            estimated_tokens=context_window.estimated_tokens,
            payload_bytes=payload_bytes,
            keep_last=compaction.keep_last,
        )
        return ListAgentContextResult(
            status=ListAgentContextStatus.OK,
            run_id=run_id,
            agent_id=agent_id,
            context_id=agent.context_id,
            window=window,
            entries=items,
        )

    def _resolve_agent_config_path(self, source: str, ref: str) -> Path | None:
        try:
            config_path = self.skill_runner.resolve_file_path(source, ref, "agent.json")
        except (FileNotFoundError, ValueError):
            return None

        if config_path.exists():
            return config_path
        return None


def _to_context_item(entry: AgentContextEntry) -> AgentContextEntryItem:
    return AgentContextEntryItem(
        sequence=entry.sequence,
        role=_role(entry),
        type=_entry_display_type(entry),
        delta_tokens=entry.delta_tokens,
        delta_compact_tokens=entry.delta_compact_tokens,
        payload_bytes=_payload_bytes(entry),
        usage=entry.usage is not None,
        prunable=_prunable(entry),
        window_start_sequence=entry.window_start_sequence,
        window_base=entry.window_base,
    )


def _payload_bytes(entry: AgentContextEntry) -> int:
    payload = agent_context_payload_to_dict(entry.payload)
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return len(serialized.encode("utf-8"))


def _role(entry: AgentContextEntry) -> str:
    if entry.entry_type == AgentContextEntryType.USER_MESSAGE:
        return "user"
    if entry.entry_type == AgentContextEntryType.ASSISTANT_MESSAGE:
        return "assistant"
    return "tool"


def _entry_display_type(entry: AgentContextEntry) -> str:
    if entry.entry_type == AgentContextEntryType.USER_MESSAGE:
        return "message"
    if entry.entry_type == AgentContextEntryType.ASSISTANT_MESSAGE:
        if entry.message_type is None:
            return "message"
        return entry.message_type.value
    return entry.entry_type.value


def _prunable(entry: AgentContextEntry) -> bool:
    if entry.entry_type in {AgentContextEntryType.TOOL_CALL, AgentContextEntryType.TOOL_RESULT}:
        return True
    return (
        entry.entry_type == AgentContextEntryType.ASSISTANT_MESSAGE
        and entry.message_type == AgentAssistantMessageType.TOOL_CALLS
    )


def _start_sequence(entries: list[AgentContextEntry]) -> int:
    if not entries:
        return 0
    return entries[0].sequence


def _end_sequence(entries: list[AgentContextEntry]) -> int:
    if not entries:
        return 0
    return entries[-1].sequence
