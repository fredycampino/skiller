from __future__ import annotations

from dataclasses import dataclass

from skiller.interfaces.tui.adapter.cli_agent_adapter import CliAgentAdapter
from skiller.interfaces.tui.adapter.cli_invoker import CliInvoker
from skiller.interfaces.tui.adapter.cli_run_adapter import CliRunAdapter
from skiller.interfaces.tui.adapter.cli_runs_adapter import CliRunsAdapter
from skiller.interfaces.tui.adapter.cli_waiting_adapter import CliWaitingAdapter
from skiller.interfaces.tui.adapter.default_agent_port import DefaultAgentPort
from skiller.interfaces.tui.adapter.default_run_port import DefaultRunPort
from skiller.interfaces.tui.adapter.default_runs_port import DefaultRunsPort
from skiller.interfaces.tui.adapter.default_waiting_port import DefaultWaitingPort
from skiller.interfaces.tui.adapter.polling_event_observer import PollingEventObserver
from skiller.interfaces.tui.port.agent_port import AgentPort
from skiller.interfaces.tui.port.run_port import RunPort
from skiller.interfaces.tui.port.runs_port import RunsPort
from skiller.interfaces.tui.port.waiting_port import WaitingPort
from skiller.interfaces.tui.screen.theme import DEFAULT_TUI_THEME, TuiTheme
from skiller.interfaces.tui.usecase.autocomplete_use_case import AutocompleteUseCase
from skiller.interfaces.tui.usecase.list_runs_use_case import ListRunsUseCase
from skiller.interfaces.tui.usecase.move_completion_use_case import (
    MoveCompletionUseCase,
)
from skiller.interfaces.tui.usecase.normalize_command_use_case import (
    NormalizeCommandUseCase,
)
from skiller.interfaces.tui.usecase.polling_event_reducer_use_case import (
    PollingEventReducerUseCase,
)
from skiller.interfaces.tui.usecase.prompt_enter_use_case import PromptEnterUseCase
from skiller.interfaces.tui.usecase.run_command_use_case import RunCommandUseCase
from skiller.interfaces.tui.usecase.run_event_context import RunEventContext
from skiller.interfaces.tui.usecase.select_runs_table_row_use_case import (
    SelectRunsTableRowUseCase,
)
from skiller.interfaces.tui.usecase.submit_waiting_input_use_case import (
    SubmitWaitingInputUseCase,
)
from skiller.interfaces.tui.viewmodel.console_screen_viewmodel import (
    ConsoleScreenViewModel,
)


@dataclass(frozen=True)
class TuiUseCases:
    autocomplete_use_case: AutocompleteUseCase
    move_completion_use_case: MoveCompletionUseCase
    list_runs_use_case: ListRunsUseCase
    normalize_command_use_case: NormalizeCommandUseCase
    polling_event_reducer_use_case: PollingEventReducerUseCase
    prompt_enter_use_case: PromptEnterUseCase
    run_command_use_case: RunCommandUseCase
    select_runs_table_row_use_case: SelectRunsTableRowUseCase
    submit_waiting_input_use_case: SubmitWaitingInputUseCase


@dataclass(frozen=True)
class TuiContainer:
    theme: TuiTheme
    run_port: RunPort
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
            move_completion_use_case=self.use_cases.move_completion_use_case,
            list_runs_use_case=self.use_cases.list_runs_use_case,
            normalize_command_use_case=self.use_cases.normalize_command_use_case,
            polling_event_reducer_use_case=self.use_cases.polling_event_reducer_use_case,
            prompt_enter_use_case=self.use_cases.prompt_enter_use_case,
            run_command_use_case=self.use_cases.run_command_use_case,
            select_runs_table_row_use_case=self.use_cases.select_runs_table_row_use_case,
            submit_waiting_input_use_case=self.use_cases.submit_waiting_input_use_case,
        )


def build_tui_container(
    *,
    theme: TuiTheme = DEFAULT_TUI_THEME,
    run_port: RunPort | None = None,
    runs_port: RunsPort | None = None,
    waiting_port: WaitingPort | None = None,
    agent_port: AgentPort | None = None,
    cli_invoker: CliInvoker | None = None,
) -> TuiContainer:
    resolved_cli_invoker = cli_invoker or CliInvoker()
    resolved_run_port = run_port or DefaultRunPort(
        command_adapter=CliRunAdapter(invoker=resolved_cli_invoker),
        event_observer=PollingEventObserver(invoker=resolved_cli_invoker),
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
    run_event_context = RunEventContext()
    use_cases = TuiUseCases(
        autocomplete_use_case=AutocompleteUseCase(),
        move_completion_use_case=MoveCompletionUseCase(),
        list_runs_use_case=ListRunsUseCase(runs_port=resolved_runs_port),
        normalize_command_use_case=NormalizeCommandUseCase(),
        polling_event_reducer_use_case=PollingEventReducerUseCase(
            context=run_event_context,
        ),
        prompt_enter_use_case=PromptEnterUseCase(),
        run_command_use_case=RunCommandUseCase(
            run_port=resolved_run_port,
            context=run_event_context,
        ),
        select_runs_table_row_use_case=SelectRunsTableRowUseCase(
            run_port=resolved_run_port,
            context=run_event_context,
        ),
        submit_waiting_input_use_case=SubmitWaitingInputUseCase(
            waiting_port=resolved_waiting_port,
            run_port=resolved_run_port,
            context=run_event_context,
        ),
    )
    return TuiContainer(
        theme=theme,
        run_port=resolved_run_port,
        runs_port=resolved_runs_port,
        waiting_port=resolved_waiting_port,
        agent_port=resolved_agent_port,
        run_event_context=run_event_context,
        use_cases=use_cases,
    )
