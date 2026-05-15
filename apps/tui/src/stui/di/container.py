from __future__ import annotations

from dataclasses import dataclass

from stui.adapter.cli_agent_adapter import CliAgentAdapter
from stui.adapter.cli_invoker import CliInvoker
from stui.adapter.cli_run_adapter import CliRunAdapter
from stui.adapter.cli_runs_adapter import CliRunsAdapter
from stui.adapter.cli_waiting_adapter import CliWaitingAdapter
from stui.adapter.default_agent_port import DefaultAgentPort
from stui.adapter.default_events_port import DefaultEventsPort
from stui.adapter.default_run_port import DefaultRunPort
from stui.adapter.default_runs_port import DefaultRunsPort
from stui.adapter.default_waiting_port import DefaultWaitingPort
from stui.adapter.events.cli_log_event_adapter import CliLogEventAdapter
from stui.adapter.events.logs_event_observer import LogsEventObserver
from stui.port.agent_port import AgentPort
from stui.port.event_port import EventsPort
from stui.port.run_port import RunPort
from stui.port.runs_port import RunsPort
from stui.port.waiting_port import WaitingPort
from stui.screen.theme import DEFAULT_TUI_THEME, TuiTheme
from stui.usecase.autocomplete_use_case import AutocompleteUseCase
from stui.usecase.event_state_use_case import EventStateUseCase
from stui.usecase.interrupt_agent_turn_use_case import (
    InterruptAgentTurnUseCase,
)
from stui.usecase.list_runs_use_case import ListRunsUseCase
from stui.usecase.move_completion_use_case import (
    MoveCompletionUseCase,
)
from stui.usecase.normalize_command_use_case import (
    NormalizeCommandUseCase,
)
from stui.usecase.project_transcript_use_case import (
    ProjectTranscriptUseCase,
)
from stui.usecase.prompt_enter_use_case import PromptEnterUseCase
from stui.usecase.run_command_use_case import RunCommandUseCase
from stui.usecase.run_event_context import RunEventContext, RunMode, RunStatus
from stui.usecase.select_runs_table_row_use_case import (
    SelectRunsTableRowUseCase,
)
from stui.usecase.submit_waiting_input_use_case import (
    SubmitWaitingInputUseCase,
)
from stui.viewmodel.console_screen_viewmodel import (
    ConsoleScreenViewModel,
)


@dataclass(frozen=True)
class TuiUseCases:
    autocomplete_use_case: AutocompleteUseCase
    interrupt_agent_turn_use_case: InterruptAgentTurnUseCase
    move_completion_use_case: MoveCompletionUseCase
    list_runs_use_case: ListRunsUseCase
    normalize_command_use_case: NormalizeCommandUseCase
    event_state_use_case: EventStateUseCase
    project_transcript_use_case: ProjectTranscriptUseCase
    prompt_enter_use_case: PromptEnterUseCase
    run_command_use_case: RunCommandUseCase
    select_runs_table_row_use_case: SelectRunsTableRowUseCase
    submit_waiting_input_use_case: SubmitWaitingInputUseCase


@dataclass(frozen=True)
class TuiContainer:
    theme: TuiTheme
    run_port: RunPort
    events_port: EventsPort
    runs_port: RunsPort
    waiting_port: WaitingPort
    agent_port: AgentPort
    run_event_context: RunEventContext
    use_cases: TuiUseCases

    def build_viewmodel(self, *, session_key: str) -> ConsoleScreenViewModel:
        return ConsoleScreenViewModel(
            session_key=session_key,
            run_event_context=self.run_event_context,
            autocomplete_use_case=self.use_cases.autocomplete_use_case,
            interrupt_agent_turn_use_case=self.use_cases.interrupt_agent_turn_use_case,
            move_completion_use_case=self.use_cases.move_completion_use_case,
            list_runs_use_case=self.use_cases.list_runs_use_case,
            normalize_command_use_case=self.use_cases.normalize_command_use_case,
            event_state_use_case=self.use_cases.event_state_use_case,
            project_transcript_use_case=self.use_cases.project_transcript_use_case,
            prompt_enter_use_case=self.use_cases.prompt_enter_use_case,
            run_command_use_case=self.use_cases.run_command_use_case,
            select_runs_table_row_use_case=self.use_cases.select_runs_table_row_use_case,
            submit_waiting_input_use_case=self.use_cases.submit_waiting_input_use_case,
        )


def build_tui_container(
    *,
    theme: TuiTheme = DEFAULT_TUI_THEME,
    run_port: RunPort | None = None,
    events_port: EventsPort | None = None,
    runs_port: RunsPort | None = None,
    waiting_port: WaitingPort | None = None,
    agent_port: AgentPort | None = None,
    cli_invoker: CliInvoker | None = None,
) -> TuiContainer:
    resolved_cli_invoker = cli_invoker or CliInvoker()
    resolved_run_port = run_port or DefaultRunPort(
        command_adapter=CliRunAdapter(invoker=resolved_cli_invoker),
    )
    resolved_events_port = events_port or DefaultEventsPort(
        event_observer=LogsEventObserver(
            logs=CliLogEventAdapter(invoker=resolved_cli_invoker),
            run_port=resolved_run_port,
        ),
    )
    resolved_runs_port = runs_port or DefaultRunsPort(
        command_adapter=CliRunsAdapter(invoker=resolved_cli_invoker),
    )
    resolved_waiting_port = waiting_port or DefaultWaitingPort(
        command_adapter=CliWaitingAdapter(invoker=resolved_cli_invoker),
    )
    resolved_agent_port = agent_port or DefaultAgentPort(
        command_adapter=CliAgentAdapter(invoker=resolved_cli_invoker),
    )
    run_event_context = RunEventContext(
        run_id="",
        skill_name="",
        mode=RunMode.FLOW,
        status=RunStatus.RUNNING,
    )
    use_cases = TuiUseCases(
        autocomplete_use_case=AutocompleteUseCase(),
        interrupt_agent_turn_use_case=InterruptAgentTurnUseCase(
            agent_port=resolved_agent_port,
        ),
        move_completion_use_case=MoveCompletionUseCase(),
        list_runs_use_case=ListRunsUseCase(runs_port=resolved_runs_port),
        normalize_command_use_case=NormalizeCommandUseCase(),
        event_state_use_case=EventStateUseCase(context=run_event_context),
        project_transcript_use_case=ProjectTranscriptUseCase(),
        prompt_enter_use_case=PromptEnterUseCase(),
        run_command_use_case=RunCommandUseCase(
            run_port=resolved_run_port,
            events_port=resolved_events_port,
            context=run_event_context,
        ),
        select_runs_table_row_use_case=SelectRunsTableRowUseCase(
            run_port=resolved_run_port,
            events_port=resolved_events_port,
            context=run_event_context,
        ),
        submit_waiting_input_use_case=SubmitWaitingInputUseCase(
            waiting_port=resolved_waiting_port,
            run_port=resolved_run_port,
            events_port=resolved_events_port,
            context=run_event_context,
        ),
    )
    return TuiContainer(
        theme=theme,
        run_port=resolved_run_port,
        events_port=resolved_events_port,
        runs_port=resolved_runs_port,
        waiting_port=resolved_waiting_port,
        agent_port=resolved_agent_port,
        run_event_context=run_event_context,
        use_cases=use_cases,
    )
