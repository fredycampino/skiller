from __future__ import annotations

import pytest

from stui.usecase.get_run_action_use_case import GetRunActionUseCase
from stui.usecase.normalize_command_use_case import Command, CommandKind
from stui.usecase.run_event_context import RunEventContext, RunMode, RunStatus
from stui.viewmodel.console_screen_state import (
    ActionOpenUrlItem,
    ActionRunItem,
    ConsoleScreenState,
    NotifyActionDoneItem,
    RunFinishedItem,
    StepNotifyActionItem,
    StepOutputItem,
)

pytestmark = pytest.mark.unit


def _use_case() -> GetRunActionUseCase:
    return GetRunActionUseCase(
        context=RunEventContext(
            run_id="run-1",
            run_name="run",
            mode=RunMode.FLOW,
            status=RunStatus.RUNNING,
        )
    )


def test_get_run_action_returns_run_finished_command() -> None:
    state = ConsoleScreenState()
    state.transcript.items.append(
        RunFinishedItem(
            run_id="run-1",
            status="succeeded",
            action=ActionRunItem(
                uid="action-run-1",
                type="run",
                label="Run next",
                arg="ci",
                params="--fast",
            ),
        )
    )

    result = _use_case().execute(state=state)

    assert result.command == Command(
        kind=CommandKind.RUN,
        name="/run",
        raw_text="/run ci --fast",
        args_text="ci --fast",
    )
    assert result.run_id == ""
    assert result.action_uid == ""


def test_get_run_action_returns_notify_run_command() -> None:
    state = ConsoleScreenState()
    state.transcript.items.append(
        StepNotifyActionItem(
            run_id="run-1",
            step_id="notify_run",
            step_type="notify",
            message="Run child",
            action=ActionRunItem(
                uid="action-run-1",
                type="run",
                label="Run child",
                arg="--file child.yaml",
                params="--arg message=hello",
            ),
        )
    )

    result = _use_case().execute(state=state)

    assert result.command == Command(
        kind=CommandKind.RUN,
        name="/run",
        raw_text="/run --file child.yaml --arg message=hello",
        args_text="--file child.yaml --arg message=hello",
    )
    assert result.run_id == "run-1"
    assert result.action_uid == "action-run-1"


def test_get_run_action_returns_notify_run_command_before_run_finished() -> None:
    state = ConsoleScreenState()
    state.transcript.items.extend(
        [
            StepNotifyActionItem(
                run_id="run-1",
                step_id="notify_run",
                step_type="notify",
                message="Run child",
                action=ActionRunItem(
                    uid="action-run-1",
                    type="run",
                    label="Run child",
                    arg="--file child.yaml",
                ),
            ),
            RunFinishedItem(
                run_id="run-1",
                status="succeeded",
            ),
        ]
    )

    result = _use_case().execute(state=state)

    assert result.command == Command(
        kind=CommandKind.RUN,
        name="/run",
        raw_text="/run --file child.yaml",
        args_text="--file child.yaml",
    )
    assert result.run_id == "run-1"
    assert result.action_uid == "action-run-1"


def test_get_run_action_ignores_notify_run_when_done_exists_in_same_batch() -> None:
    state = ConsoleScreenState()
    state.transcript.items.extend(
        [
            NotifyActionDoneItem(
                run_id="run-1",
                action_uid="action-run-1",
                type="run",
                status="done",
            ),
            StepNotifyActionItem(
                run_id="run-1",
                step_id="notify_run",
                step_type="notify",
                message="Run child",
                action=ActionRunItem(
                    uid="action-run-1",
                    type="run",
                    label="Run child",
                    arg="child",
                ),
            ),
        ]
    )
    use_case = _use_case()

    result = use_case.execute(state=state)

    assert result.command is None
    assert use_case.context.actions_done == {"action-run-1"}


def test_get_run_action_ignores_action_already_done_in_context() -> None:
    state = ConsoleScreenState()
    state.transcript.items.append(
        StepNotifyActionItem(
            run_id="run-1",
            step_id="notify_run",
            step_type="notify",
            message="Run child",
            action=ActionRunItem(
                uid="action-run-1",
                type="run",
                label="Run child",
                arg="child",
            ),
        )
    )
    context = RunEventContext(
        run_id="run-1",
        run_name="run",
        mode=RunMode.FLOW,
        status=RunStatus.RUNNING,
        actions_done={"action-run-1"},
    )

    result = GetRunActionUseCase(context=context).execute(state=state)

    assert result.command is None


def test_get_run_action_marks_resolved_action_done_in_context() -> None:
    state = ConsoleScreenState()
    state.transcript.items.append(
        StepNotifyActionItem(
            run_id="run-1",
            step_id="notify_run",
            step_type="notify",
            message="Run child",
            action=ActionRunItem(
                uid="action-run-1",
                type="run",
                label="Run child",
                arg="child",
            ),
        )
    )
    context = RunEventContext(
        run_id="run-1",
        run_name="run",
        mode=RunMode.FLOW,
        status=RunStatus.RUNNING,
    )

    result = GetRunActionUseCase(context=context).execute(state=state)

    assert result.command is not None
    assert context.actions_done == {"action-run-1"}


def test_get_run_action_returns_none_when_last_item_is_not_action() -> None:
    state = ConsoleScreenState()
    state.transcript.items.extend(
        [
            RunFinishedItem(
                run_id="run-1",
                status="succeeded",
                action=ActionRunItem(
                    uid="action-run-1",
                    type="run",
                    label="Run next",
                    arg="ci",
                ),
            ),
            StepOutputItem(run_id="run-1", step_type="notify", output="done"),
        ]
    )

    result = _use_case().execute(state=state)

    assert result.command is None


def test_get_run_action_returns_none_for_other_action_type() -> None:
    state = ConsoleScreenState()
    state.transcript.items.append(
        RunFinishedItem(
            run_id="run-1",
            status="succeeded",
            action=ActionOpenUrlItem(
                uid="action-open-1",
                type="open_url",
                label="Open",
                url="https://example.com",
            ),
        )
    )

    result = _use_case().execute(state=state)

    assert result.command is None
