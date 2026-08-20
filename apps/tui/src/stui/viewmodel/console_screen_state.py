from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum

from stui.port.event_models import ActionPostArg
from stui.port.models_port import AuthProvidersPortProviderItem, ModelsPortProviderItem
from stui.port.runs_port import RunsPortItem


class TranscriptMode(StrEnum):
    FLOW = "flow"
    CHAT = "chat"


class PromptMode(StrEnum):
    DEFAULT = "default"
    AUTOCOMPLETION = "autocompletion"
    RUNS_TABLE = "runs_table"
    MODELS_TABLE = "models_table"
    AUTH_TABLE = "auth_table"
    INTERRUPT_PENDING = "interrupt_pending"


class ViewStatusKind(StrEnum):
    HIDDEN = "hidden"
    WAITING = "waiting"
    RUNNING = "running"
    ERROR = "error"


class OutputFormat(StrEnum):
    SIMPLE = "simple"
    STRUCTURED = "structured"
    MARKDOWN = "markdown"


class AgentStepStopReason(StrEnum):
    FINAL = "final"
    INTERRUPTED = "interrupted"
    MAX_TURNS_EXHAUSTED = "max_turns_exhausted"
    CONFIG_INVALID = "config_invalid"
    LLM_REQUEST_FAILED = "llm_request_failed"


class RunSnapshotStatus(StrEnum):
    UPDATED = "updated"
    FAILED = "failed"


@dataclass(frozen=True)
class TranscriptItem:
    sequence: int | None = field(default=None, kw_only=True)


@dataclass(frozen=True)
class UserInputItem(TranscriptItem):
    text: str


@dataclass(frozen=True)
class InfoItem(TranscriptItem):
    text: str


@dataclass(frozen=True)
class DispatchErrorItem(TranscriptItem):
    message: str


@dataclass(frozen=True)
class RunAckItem(TranscriptItem):
    skill: str
    run_id: str


@dataclass(frozen=True)
class RunResumeItem(TranscriptItem):
    run_id: str
    skill: str


@dataclass(frozen=True)
class RunStepItem(TranscriptItem):
    run_id: str
    step_type: str
    step_id: str


@dataclass(frozen=True)
class AgentToolCallItem(TranscriptItem):
    run_id: str
    step_id: str
    tool: str
    command: str


@dataclass(frozen=True)
class AgentToolResultItem(TranscriptItem):
    run_id: str
    tool: str
    preview: str
    has_more: bool = True


@dataclass(frozen=True)
class AgentContextCompactedItem(TranscriptItem):
    run_id: str
    context_id: str
    compaction_id: int
    system_tokens: int
    estimated_request_tokens: int
    estimated_request_compacted_tokens: int
    target_tokens: int
    window_tokens: int


@dataclass(frozen=True)
class AgentAssistantMessageItem(TranscriptItem):
    run_id: str
    step_id: str
    message_type: str
    text: str
    total_tokens: int
    usage: AgentStepUsage | None
    context: AgentStepContext | None
    format: OutputFormat = OutputFormat.MARKDOWN


@dataclass(frozen=True)
class AgentFinalAssistantMessageItem(TranscriptItem):
    run_id: str
    step_id: str
    text: str
    total_tokens: int
    usage: AgentStepUsage | None
    context: AgentStepContext | None
    format: OutputFormat = OutputFormat.MARKDOWN


@dataclass(frozen=True)
class AgentStepUsage:
    prompt_tokens: int | None
    estimated_system_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    cache_read_tokens: int | None
    cache_write_tokens: int | None
    provider: str | None
    model: str | None


@dataclass(frozen=True)
class AgentStepContext:
    effective_window_tokens: int | None
    max_total_tokens_ratio: float | None


@dataclass(frozen=True)
class AgentStepFinalOutputItem(TranscriptItem):
    run_id: str
    step_id: str
    stop_reason: AgentStepStopReason
    final: str
    usage: AgentStepUsage | None
    context: AgentStepContext | None
    format: OutputFormat = OutputFormat.MARKDOWN


@dataclass(frozen=True)
class AgentSystemNoticeItem(TranscriptItem):
    run_id: str
    step_id: str
    text: str
    format: OutputFormat = OutputFormat.SIMPLE


@dataclass(frozen=True)
class RunSyncSnapshotItem(TranscriptItem):
    run_id: str
    source: str
    ref: str
    status: RunSnapshotStatus
    error: str = ""


@dataclass(frozen=True)
class RunModelUpdatedItem(TranscriptItem):
    run_id: str
    provider: str
    model: str


@dataclass(frozen=True)
class RunOutputItem(TranscriptItem):
    run_id: str
    step_type: str
    output: str
    format: OutputFormat = OutputFormat.SIMPLE


@dataclass(frozen=True)
class StepOutputItem(TranscriptItem):
    run_id: str
    step_type: str
    output: str
    format: OutputFormat = OutputFormat.SIMPLE
    icon: str = "•"
    muted: bool = False


@dataclass(frozen=True)
class StepNotifyOutputItem(TranscriptItem):
    run_id: str
    step_type: str
    message: str
    format: OutputFormat = OutputFormat.SIMPLE
    icon: str = "•"
    muted: bool = False


@dataclass(frozen=True)
class ActionItem:
    uid: str
    type: str
    label: str


@dataclass(frozen=True)
class ActionOpenUrlItem(ActionItem):
    message: str | None = None
    url: str = ""
    auto: bool = False


@dataclass(frozen=True)
class ActionRunItem(ActionItem):
    arg: str
    params: str | None = None
    auto: bool = False


@dataclass(frozen=True)
class ActionPostItem(ActionItem):
    arg: ActionPostArg
    params: str | None = None
    auto: bool = False


ActionTranscriptItem = ActionOpenUrlItem | ActionRunItem | ActionPostItem | ActionItem


@dataclass(frozen=True)
class StepNotifyActionItem(TranscriptItem):
    run_id: str
    step_id: str
    step_type: str
    message: str
    action: ActionTranscriptItem


@dataclass(frozen=True)
class NotifyActionDoneItem(TranscriptItem):
    run_id: str
    action_uid: str
    type: str
    status: str


@dataclass(frozen=True)
class StepShellOutputItem(TranscriptItem):
    run_id: str
    step_type: str
    output: str
    format: OutputFormat = OutputFormat.SIMPLE
    icon: str = "▫"
    muted: bool = False


@dataclass(frozen=True)
class StepErrorItem(TranscriptItem):
    run_id: str
    step_id: str
    step_type: str
    message: str


@dataclass(frozen=True)
class RunFinishedItem(TranscriptItem):
    run_id: str
    status: str
    message: str = ""
    action: ActionTranscriptItem | None = None


@dataclass(frozen=True)
class RunWaitingInputItem(TranscriptItem):
    run_id: str
    step_type: str
    step_id: str
    prompt: str = ""


@dataclass(frozen=True)
class RunWaitingWebhookItem(TranscriptItem):
    run_id: str
    step_type: str
    step_id: str
    webhook: str
    key: str
    icon: str = "↯"
    muted: bool = False


@dataclass(frozen=True)
class CompletionItem:
    label: str
    description: str = ""
    insert_text: str = ""
    kind: str = ""


@dataclass(frozen=True)
class CompletionState:
    visible: bool
    query: str
    items: tuple[CompletionItem, ...]
    selected_index: int = 0
    replace_from: int = 0
    replace_to: int = 0

    @property
    def selected_item(self) -> CompletionItem | None:
        if not self.items:
            return None
        if self.selected_index < 0 or self.selected_index >= len(self.items):
            return None
        return self.items[self.selected_index]


@dataclass
class TranscriptState:
    mode: TranscriptMode = TranscriptMode.CHAT
    items: list[TranscriptItem] = field(default_factory=list)


@dataclass
class PromptState:
    mode: PromptMode = PromptMode.DEFAULT
    text: str = ""
    cursor_position: int = 0


@dataclass
class RunsTableState:
    visible: bool = False
    command: str = ""
    rows: tuple[RunsPortItem, ...] = field(default_factory=tuple)


@dataclass
class ModelsTableState:
    visible: bool = False
    command: str = ""
    rows: tuple[ModelsPortProviderItem, ...] = field(default_factory=tuple)


@dataclass
class AuthTableState:
    visible: bool = False
    command: str = ""
    rows: tuple[AuthProvidersPortProviderItem, ...] = field(default_factory=tuple)


@dataclass
class AgentMetricsState:
    usage: AgentStepUsage | None
    context: AgentStepContext | None


@dataclass
class AgentContextStatsState:
    entries: int
    estimated_tokens: int
    start_sequence: int
    end_sequence: int
    current_tokens: int
    limit_tokens: int
    capacity_tokens: int


@dataclass
class ViewStatusState:
    kind: ViewStatusKind = ViewStatusKind.HIDDEN
    message: str = ""


@dataclass(frozen=True)
class NotifyActionState:
    run_id: str
    message: str
    action: ActionOpenUrlItem


@dataclass
class ConsoleScreenState:
    session_key: str = "main"
    run_name: str = ""
    transcript: TranscriptState = field(default_factory=TranscriptState)
    prompt: PromptState = field(default_factory=PromptState)
    runs_table: RunsTableState = field(default_factory=RunsTableState)
    models_table: ModelsTableState = field(default_factory=ModelsTableState)
    auth_table: AuthTableState = field(default_factory=AuthTableState)
    agent_metrics: AgentMetricsState | None = None
    agent_context_stats: AgentContextStatsState | None = None
    view_status: ViewStatusState = field(default_factory=ViewStatusState)
    autocompletion: CompletionState | None = None
    notify_action: NotifyActionState | None = None

    def set_prompt(
        self,
        *,
        text: str = "",
        cursor_position: int = 0,
        mode: PromptMode = PromptMode.DEFAULT,
    ) -> None:
        self.prompt.text = text
        self.prompt.cursor_position = cursor_position
        self.prompt.mode = mode

    def set_transcript(
        self,
        *,
        mode: TranscriptMode = TranscriptMode.CHAT,
        items: list[TranscriptItem] | None = None,
    ) -> None:
        self.transcript = TranscriptState(
            mode=mode,
            items=list(items or []),
        )

    def set_status(
        self,
        *,
        kind: ViewStatusKind = ViewStatusKind.HIDDEN,
        message: str = "",
    ) -> None:
        self.view_status.kind = kind
        self.view_status.message = message

    def set_autocompletion(
        self,
        autocompletion: CompletionState | None = None,
    ) -> None:
        self.autocompletion = autocompletion

    def set_runs_table(
        self,
        *,
        visible: bool = False,
        command: str = "",
        rows: Sequence[RunsPortItem] = (),
    ) -> None:
        self.runs_table.visible = visible
        self.runs_table.command = command
        self.runs_table.rows = tuple(rows)

    def set_models_table(
        self,
        *,
        visible: bool = False,
        command: str = "",
        rows: Sequence[ModelsPortProviderItem] = (),
    ) -> None:
        self.models_table.visible = visible
        self.models_table.command = command
        self.models_table.rows = tuple(rows)

    def set_auth_table(
        self,
        *,
        visible: bool = False,
        command: str = "",
        rows: Sequence[AuthProvidersPortProviderItem] = (),
    ) -> None:
        self.auth_table.visible = visible
        self.auth_table.command = command
        self.auth_table.rows = tuple(rows)

    def set_agent_metrics(self, agent_metrics: AgentMetricsState | None) -> None:
        self.agent_metrics = agent_metrics

    def set_agent_context_stats(
        self,
        agent_context_stats: AgentContextStatsState | None = None,
    ) -> None:
        self.agent_context_stats = agent_context_stats

    def set_notify_action(
        self,
        notify_action: NotifyActionState | None = None,
    ) -> None:
        self.notify_action = notify_action

    def load_session(
        self,
        *,
        run_id: str,
        run_name: str = "",
    ) -> None:
        self.agent_metrics = None
        self.session_key = run_id
        self.run_name = run_name
