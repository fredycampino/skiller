from __future__ import annotations

from dataclasses import dataclass

from stui.adapter.cli_agent_adapter import CliAgentAdapter
from stui.adapter.cli_invoker import CliInvoker
from stui.adapter.cli_notify_action_adapter import CliNotifyActionAdapter
from stui.adapter.cli_run_adapter import CliRunAdapter
from stui.adapter.cli_runs_adapter import CliRunsAdapter
from stui.adapter.cli_waiting_adapter import CliWaitingAdapter
from stui.adapter.default_agent_port import DefaultAgentPort
from stui.adapter.default_events_port import DefaultEventsPort
from stui.adapter.default_installation_state_port import DefaultInstallationStatePort
from stui.adapter.default_notify_action_port import DefaultNotifyActionPort
from stui.adapter.default_run_port import DefaultRunPort
from stui.adapter.default_runs_port import DefaultRunsPort
from stui.adapter.default_waiting_port import DefaultWaitingPort
from stui.adapter.events.cli_log_event_adapter import CliLogEventAdapter
from stui.adapter.events.logs_event_observer import LogsEventObserver
from stui.di.strings import DEFAULT_TUI_STRINGS, TuiStrings
from stui.port.agent_port import AgentPort
from stui.port.event_port import EventsPort
from stui.port.installation_state_port import InstallationStatePort
from stui.port.notify_action_port import NotifyActionPort
from stui.port.run_port import RunPort
from stui.port.runs_port import RunsPort
from stui.port.waiting_port import WaitingPort
from stui.screen.theme import DEFAULT_TUI_THEME, TuiTheme
from stui.usecase.autocomplete_use_case import AutocompleteUseCase
from stui.usecase.done_notify_action_use_case import DoneNotifyActionUseCase
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
from stui.usecase.open_notify_action_use_case import OpenNotifyActionUseCase
from stui.usecase.project_notify_action_use_case import (
    ProjectNotifyActionUseCase,
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
from stui.usecase.start_console_use_case import StartConsoleUseCase
from stui.usecase.submit_waiting_input_use_case import (
    SubmitWaitingInputUseCase,
)
from stui.usecase.unsupported_input_use_case import UnsupportedInputUseCase
from stui.viewmodel.console_screen_use_cases import ConsoleScreenUseCases
from stui.viewmodel.console_screen_viewmodel import (
    ConsoleScreenViewModel,
)


@dataclass(frozen=True)
class TuiContainer:
    theme: TuiTheme
    strings: TuiStrings
    run_port: RunPort
    events_port: EventsPort
    runs_port: RunsPort
    waiting_port: WaitingPort
    notify_action_port: NotifyActionPort
    agent_port: AgentPort
    installation_state_port: InstallationStatePort
    run_event_context: RunEventContext
    use_cases: ConsoleScreenUseCases

    def build_viewmodel(self, *, session_key: str) -> ConsoleScreenViewModel:
        return ConsoleScreenViewModel(
            session_key=session_key,
            run_event_context=self.run_event_context,
            use_cases=self.use_cases,
        )


def build_tui_container(
    *,
    theme: TuiTheme = DEFAULT_TUI_THEME,
    strings: TuiStrings = DEFAULT_TUI_STRINGS,
    run_port: RunPort | None = None,
    events_port: EventsPort | None = None,
    runs_port: RunsPort | None = None,
    waiting_port: WaitingPort | None = None,
    notify_action_port: NotifyActionPort | None = None,
    agent_port: AgentPort | None = None,
    installation_state_port: InstallationStatePort | None = None,
    cli_invoker: CliInvoker | None = None,
) -> TuiContainer:
    resolved_cli_invoker = cli_invoker or CliInvoker()
    resolved_run_port = run_port or DefaultRunPort(
        command_adapter=CliRunAdapter(invoker=resolved_cli_invoker),
    )
    resolved_agent_port = agent_port or DefaultAgentPort(
        command_adapter=CliAgentAdapter(invoker=resolved_cli_invoker),
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
    resolved_notify_action_port = notify_action_port or DefaultNotifyActionPort(
        command_adapter=CliNotifyActionAdapter(invoker=resolved_cli_invoker),
    )
    resolved_installation_state_port = (
        installation_state_port or DefaultInstallationStatePort()
    )
    run_event_context = RunEventContext(
        run_id="",
        skill_name="",
        mode=RunMode.CHAT,
        status=RunStatus.RUNNING,
    )
    use_cases = ConsoleScreenUseCases(
        autocomplete=AutocompleteUseCase(),
        interrupt_agent_turn=InterruptAgentTurnUseCase(
            agent_port=resolved_agent_port,
        ),
        move_completion=MoveCompletionUseCase(),
        list_runs=ListRunsUseCase(runs_port=resolved_runs_port),
        normalize_command=NormalizeCommandUseCase(),
        event_state=EventStateUseCase(
            context=run_event_context,
            agent_port=resolved_agent_port,
            events_port=resolved_events_port,
        ),
        done_notify_action=DoneNotifyActionUseCase(
            notify_action_port=resolved_notify_action_port,
        ),
        open_notify_action=OpenNotifyActionUseCase(
            notify_action_port=resolved_notify_action_port,
        ),
        project_notify_action=ProjectNotifyActionUseCase(),
        project_transcript=ProjectTranscriptUseCase(),
        prompt_enter=PromptEnterUseCase(),
        run_command=RunCommandUseCase(
            run_port=resolved_run_port,
            events_port=resolved_events_port,
            context=run_event_context,
        ),
        start_console=StartConsoleUseCase(
            installation_state_port=resolved_installation_state_port,
            run_port=resolved_run_port,
            events_port=resolved_events_port,
            context=run_event_context,
        ),
        select_runs_table_row=SelectRunsTableRowUseCase(
            run_port=resolved_run_port,
            events_port=resolved_events_port,
            context=run_event_context,
        ),
        submit_waiting_input=SubmitWaitingInputUseCase(
            waiting_port=resolved_waiting_port,
            run_port=resolved_run_port,
            events_port=resolved_events_port,
            context=run_event_context,
        ),
        unsupported_input=UnsupportedInputUseCase(strings=strings),
    )
    return TuiContainer(
        theme=theme,
        strings=strings,
        run_port=resolved_run_port,
        events_port=resolved_events_port,
        runs_port=resolved_runs_port,
        waiting_port=resolved_waiting_port,
        notify_action_port=resolved_notify_action_port,
        agent_port=resolved_agent_port,
        installation_state_port=resolved_installation_state_port,
        run_event_context=run_event_context,
        use_cases=use_cases,
    )
