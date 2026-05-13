from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum

from stui.port.runs_port import RunsPortItem


class TranscriptMode(StrEnum):
    FLOW = "flow"
    CHAT = "chat"


class PromptMode(StrEnum):
    DEFAULT = "default"
    AUTOCOMPLETION = "autocompletion"
    RUNS_TABLE = "runs_table"
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


@dataclass(frozen=True)
class TranscriptItem:
    pass


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
class AgentAssistantMessageItem(TranscriptItem):
    run_id: str
    step_id: str
    message_type: str
    text: str
    format: OutputFormat = OutputFormat.MARKDOWN


@dataclass(frozen=True)
class AgentSystemNoticeItem(TranscriptItem):
    run_id: str
    step_id: str
    text: str


@dataclass(frozen=True)
class RunOutputItem(TranscriptItem):
    run_id: str
    step_type: str
    output: str
    format: OutputFormat = OutputFormat.SIMPLE


@dataclass(frozen=True)
class RunStatusItem(TranscriptItem):
    run_id: str
    status: str
    message: str = ""


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
    mode: TranscriptMode = TranscriptMode.FLOW
    items: list[TranscriptItem] = field(default_factory=list)


@dataclass
class PromptState:
    mode: PromptMode = PromptMode.DEFAULT
    text: str = ""
    cursor_position: int = 0
    waiting_prompt: str = ""


@dataclass
class RunsTableState:
    visible: bool = False
    command: str = ""
    rows: tuple[RunsPortItem, ...] = field(default_factory=tuple)


@dataclass
class ViewStatusState:
    kind: ViewStatusKind = ViewStatusKind.HIDDEN
    message: str = ""


@dataclass
class ConsoleScreenState:
    session_key: str = "main"
    transcript: TranscriptState = field(default_factory=TranscriptState)
    prompt: PromptState = field(default_factory=PromptState)
    runs_table: RunsTableState = field(default_factory=RunsTableState)
    view_status: ViewStatusState = field(default_factory=ViewStatusState)
    autocompletion: CompletionState | None = None

    def set_prompt(
        self,
        *,
        text: str = "",
        cursor_position: int = 0,
        waiting_prompt: str = "",
        mode: PromptMode = PromptMode.DEFAULT,
    ) -> None:
        self.prompt.text = text
        self.prompt.cursor_position = cursor_position
        self.prompt.waiting_prompt = waiting_prompt
        self.prompt.mode = mode

    def set_transcript(
        self,
        *,
        mode: TranscriptMode = TranscriptMode.FLOW,
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

    def load_session(
        self,
        *,
        run_id: str,
    ) -> None:
        self.session_key = run_id
