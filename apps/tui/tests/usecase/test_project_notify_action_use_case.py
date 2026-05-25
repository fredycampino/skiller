from __future__ import annotations

import pytest

from stui.usecase.project_notify_action_use_case import ProjectNotifyActionUseCase
from stui.viewmodel.console_screen_state import (
    ConsoleScreenState,
    NotifyActionDoneItem,
    NotifyActionState,
    StepNotifyActionItem,
    StepNotifyOutputItem,
)

pytestmark = pytest.mark.unit


def test_project_notify_action_sets_pending_action() -> None:
    state = ConsoleScreenState()
    state.transcript.items.append(_action_item(status="pending"))

    result = ProjectNotifyActionUseCase().execute(state=state)

    assert result.state.notify_action == NotifyActionState(
        run_id="run-1",
        step_id="auth_link",
        message="Authorize the app",
        label="Open authorization",
        url="https://example.com/oauth/start",
        status="pending",
    )


def test_project_notify_action_clears_done_action() -> None:
    state = ConsoleScreenState()
    state.set_notify_action(
        NotifyActionState(
            run_id="run-1",
            step_id="auth_link",
            message="Authorize the app",
            label="Open authorization",
            url="https://example.com/oauth/start",
            status="pending",
        )
    )
    state.transcript.items.append(_action_item(status="done"))

    result = ProjectNotifyActionUseCase().execute(state=state)

    assert result.state.notify_action is None


def test_project_notify_action_clears_when_action_done_event_arrives() -> None:
    state = ConsoleScreenState()
    state.transcript.items.extend(
        [
            _action_item(status="pending"),
            NotifyActionDoneItem(
                run_id="run-1",
                step_id="auth_link",
                step_type="notify",
                action_type="open_url",
                status="done",
            ),
        ]
    )

    result = ProjectNotifyActionUseCase().execute(state=state)

    assert result.state.notify_action is None


def test_project_notify_action_keeps_pending_action_after_later_regular_notify() -> None:
    state = ConsoleScreenState()
    state.transcript.items.extend(
        [
            _action_item(status="pending"),
            StepNotifyOutputItem(
                run_id="run-1",
                step_type="notify",
                message="Regular notify",
            ),
        ]
    )

    result = ProjectNotifyActionUseCase().execute(state=state)

    assert result.state.notify_action == NotifyActionState(
        run_id="run-1",
        step_id="auth_link",
        message="Authorize the app",
        label="Open authorization",
        url="https://example.com/oauth/start",
        status="pending",
    )


def _action_item(*, status: str) -> StepNotifyActionItem:
    return StepNotifyActionItem(
        run_id="run-1",
        step_id="auth_link",
        step_type="notify",
        message="Authorize the app",
        action_type="open_url",
        label="Open authorization",
        url="https://example.com/oauth/start",
        status=status,
    )
