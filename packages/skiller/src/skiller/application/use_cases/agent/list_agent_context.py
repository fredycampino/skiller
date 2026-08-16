import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from skiller.domain.agent.config.port import AgentConfigPort
from skiller.domain.agent.context.context_state_port import AgentContextStatePort
from skiller.domain.agent.context.context_store_port import AgentContextStorePort
from skiller.domain.agent.context.model import (
    AgentAssistantMessageType,
    AgentContextEntry,
    AgentContextEntryType,
    AgentContextWindowEntries,
    AgentContextWindowQuery,
    agent_context_payload_to_dict,
)
from skiller.domain.agent.llm.provider_catalog_port import LLMProviderCatalogPort
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
    compaction_id: int | None
    payload_bytes: int
    usage: bool
    prunable: bool


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
        agent_context_state: AgentContextStatePort,
        agent_config: AgentConfigPort,
        llm_provider_catalog: LLMProviderCatalogPort,
        skill_runner: RunnerPort,
    ) -> None:
        self.run_store = run_store
        self.run_agent_store = run_agent_store
        self.agent_context_store = agent_context_store
        self.agent_context_state = agent_context_state
        self.agent_config = agent_config
        self.llm_provider_catalog = llm_provider_catalog
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
        catalog = self.llm_provider_catalog.get_catalog()
        model = catalog.get_model(
            provider_name=config.llm.provider,
            model_name=config.llm.model,
        )
        context_config = config.context
        compaction = context_config.compaction

        state = self.agent_context_state.get_state(context_id=agent.context_id)
        context_window = self._recover_context_window(state=state)

        entries = context_window.entries
        items = tuple(_to_context_item(entry) for entry in entries)
        payload_bytes = sum(item.payload_bytes for item in items)
        window = AgentContextWindow(
            mode="compact" if state.compacted_sequence is not None else "raw",
            entries=len(items),
            start_sequence=state.start_sequence,
            end_sequence=_end_sequence(entries),
            limit_tokens=context_config.compaction_trigger_tokens(
                model_context_window_tokens=model.context_window_tokens,
            ),
            estimated_tokens=context_window.estimated_tokens,
            payload_bytes=payload_bytes,
            keep_last=compaction.keep_last_blocks,
        )
        return ListAgentContextResult(
            status=ListAgentContextStatus.OK,
            run_id=run_id,
            agent_id=agent_id,
            context_id=agent.context_id,
            window=window,
            entries=items,
        )

    def _recover_context_window(
        self,
        *,
        state,
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
        compaction_id=entry.compaction_id,
        payload_bytes=_payload_bytes(entry),
        usage=entry.usage is not None,
        prunable=_prunable(entry),
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


def _end_sequence(entries: list[AgentContextEntry]) -> int:
    if not entries:
        return 0
    return entries[-1].sequence
