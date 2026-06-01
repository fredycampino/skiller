from __future__ import annotations

import pytest

from stui.usecase.normalize_command_use_case import Command, CommandKind
from stui.usecase.run_finished_action_use_case import RunFinishedActionUseCase
from stui.viewmodel.console_screen_state import (
    ActionOpenUrlItem,
    ActionRunItem,
    ConsoleScreenState,
    RunFinishedItem,
    StepOutputItem,
)

pytestmark = pytest.mark.unit


def test_run_finished_action_returns_run_command() -> None:
    state = ConsoleScreenState()
    state.transcript.items.append(
        RunFinishedItem(
            run_id="run-1",
            status="succeeded",
            action=ActionRunItem(
                type="run",
                label="Run next",
                arg="ci",
                params="--fast",
            ),
        )
    )

    result = RunFinishedActionUseCase().execute(state=state)

    assert result.command == Command(
        kind=CommandKind.RUN,
        name="/run",
        raw_text="/run ci --fast",
        args_text="ci --fast",
    )


def test_run_finished_action_returns_none_when_last_item_is_not_run_finished() -> None:
    state = ConsoleScreenState()
    state.transcript.items.extend(
        [
            RunFinishedItem(
                run_id="run-1",
                status="succeeded",
                action=ActionRunItem(type="run", label="Run next", arg="ci"),
            ),
            StepOutputItem(run_id="run-1", step_type="notify", output="done"),
        ]
    )

    result = RunFinishedActionUseCase().execute(state=state)

    assert result.command is None


def test_run_finished_action_returns_none_for_other_action_type() -> None:
    state = ConsoleScreenState()
    state.transcript.items.append(
        RunFinishedItem(
            run_id="run-1",
            status="succeeded",
            action=ActionOpenUrlItem(
                type="open_url",
                label="Open",
                url="https://example.com",
            ),
        )
    )

    result = RunFinishedActionUseCase().execute(state=state)

    assert result.command is None
