from __future__ import annotations

from dataclasses import dataclass

from stui.usecase.agent_status_use_case import AgentStatusUseCase
from stui.usecase.autocomplete_use_case import AutocompleteUseCase
from stui.usecase.done_notify_action_use_case import DoneNotifyActionUseCase
from stui.usecase.event_state_use_case import EventStateUseCase
from stui.usecase.get_run_action_use_case import GetRunActionUseCase
from stui.usecase.interrupt_agent_turn_use_case import (
    InterruptAgentTurnUseCase,
)
from stui.usecase.list_runs_use_case import ListRunsUseCase
from stui.usecase.move_completion_use_case import (
    MoveCompletionUseCase,
)
from stui.usecase.normalize_command_use_case import NormalizeCommandUseCase
from stui.usecase.open_notify_action_use_case import OpenNotifyActionUseCase
from stui.usecase.project_agent_usage_use_case import ProjectAgentUsageUseCase
from stui.usecase.project_notify_action_use_case import (
    ProjectNotifyActionUseCase,
)
from stui.usecase.project_transcript_use_case import (
    ProjectTranscriptUseCase,
)
from stui.usecase.prompt_enter_use_case import PromptEnterUseCase
from stui.usecase.run_command_use_case import RunCommandUseCase
from stui.usecase.select_runs_table_row_use_case import (
    SelectRunsTableRowUseCase,
)
from stui.usecase.start_console_use_case import StartConsoleUseCase
from stui.usecase.submit_waiting_input_use_case import (
    SubmitWaitingInputUseCase,
)
from stui.usecase.toggle_agent_stats_use_case import (
    ToggleAgentStatsUseCase,
)
from stui.usecase.unsupported_input_use_case import UnsupportedInputUseCase


@dataclass(frozen=True)
class ConsoleScreenUseCases:
    agent_status: AgentStatusUseCase
    autocomplete: AutocompleteUseCase
    interrupt_agent_turn: InterruptAgentTurnUseCase
    move_completion: MoveCompletionUseCase
    list_runs: ListRunsUseCase
    normalize_command: NormalizeCommandUseCase
    event_state: EventStateUseCase
    done_notify_action: DoneNotifyActionUseCase
    open_notify_action: OpenNotifyActionUseCase
    prompt_enter: PromptEnterUseCase
    agent_usage: ProjectAgentUsageUseCase
    notify_action: ProjectNotifyActionUseCase
    transcript: ProjectTranscriptUseCase
    run_command: RunCommandUseCase
    get_run_action: GetRunActionUseCase
    start_console: StartConsoleUseCase
    submit_waiting_input: SubmitWaitingInputUseCase
    toggle_agent_stats: ToggleAgentStatsUseCase
    unsupported_input: UnsupportedInputUseCase
    select_runs_table_row: SelectRunsTableRowUseCase
