from __future__ import annotations

import pytest

from stui.usecase.project_notify_action_use_case import ProjectNotifyActionUseCase
from stui.viewmodel.console_screen_state import (
    ActionItem,
    ActionOpenUrlItem,
    ConsoleScreenState,
    NotifyActionDoneItem,
    NotifyActionState,
    StepNotifyActionItem,
    StepNotifyOutputItem,
)

pytestmark = pytest.mark.unit


def test_project_notify_action_sets_pending_action() -> None:
    state = ConsoleScreenState()
    state.transcript.items.append(_action_item())

    result = ProjectNotifyActionUseCase().execute(state=state)

    assert result.state.notify_action == NotifyActionState(
        run_id="run-1",
        step_id="auth_link",
        message="Open the authorization link.",
        action=ActionOpenUrlItem(
            type="open_url",
            label="Open authorization",
            message="Open the authorization link.",
            url="https://example.com/oauth/start",
        ),
    )


def test_project_notify_action_clears_when_action_done_event_arrives() -> None:
    state = ConsoleScreenState()
    state.transcript.items.extend(
        [
            _action_item(),
            NotifyActionDoneItem(
                run_id="run-1",
                step_id="auth_link",
                step_type="notify",
                type="open_url",
                status="done",
            ),
        ]
    )

    result = ProjectNotifyActionUseCase().execute(state=state)

    assert result.state.notify_action is None


def test_project_notify_action_ignores_done_before_latest_action() -> None:
    state = ConsoleScreenState()
    state.transcript.items.extend(
        [
            _action_item(sequence=1),
            NotifyActionDoneItem(
                sequence=2,
                run_id="run-1",
                step_id="auth_link",
                step_type="notify",
                type="open_url",
                status="done",
            ),
            _action_item(sequence=3),
        ]
    )

    result = ProjectNotifyActionUseCase().execute(state=state)

    assert result.state.notify_action == NotifyActionState(
        run_id="run-1",
        step_id="auth_link",
        message="Open the authorization link.",
        action=ActionOpenUrlItem(
            type="open_url",
            label="Open authorization",
            message="Open the authorization link.",
            url="https://example.com/oauth/start",
        ),
    )


def test_project_notify_action_ignores_done_for_other_action_type() -> None:
    state = ConsoleScreenState()
    state.transcript.items.extend(
        [
            _action_item(),
            NotifyActionDoneItem(
                run_id="run-1",
                step_id="auth_link",
                step_type="notify",
                type="run",
                status="done",
            ),
        ]
    )

    result = ProjectNotifyActionUseCase().execute(state=state)

    assert result.state.notify_action == NotifyActionState(
        run_id="run-1",
        step_id="auth_link",
        message="Open the authorization link.",
        action=ActionOpenUrlItem(
            type="open_url",
            label="Open authorization",
            message="Open the authorization link.",
            url="https://example.com/oauth/start",
        ),
    )


def test_project_notify_action_keeps_pending_action_after_later_regular_notify() -> None:
    state = ConsoleScreenState()
    state.transcript.items.extend(
        [
            _action_item(),
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
        message="Open the authorization link.",
        action=ActionOpenUrlItem(
            type="open_url",
            label="Open authorization",
            message="Open the authorization link.",
            url="https://example.com/oauth/start",
        ),
    )


def test_project_notify_action_uses_empty_message_when_action_has_no_message() -> None:
    state = ConsoleScreenState()
    state.transcript.items.append(_action_item_without_action_message())

    result = ProjectNotifyActionUseCase().execute(state=state)

    assert result.state.notify_action == NotifyActionState(
        run_id="run-1",
        step_id="auth_link",
        message="",
        action=ActionOpenUrlItem(
            type="open_url",
            label="Open authorization",
            url="https://example.com/oauth/start",
        ),
    )


def test_project_notify_action_ignores_non_open_url_action() -> None:
    state = ConsoleScreenState()
    state.transcript.items.append(
        StepNotifyActionItem(
            run_id="run-1",
            step_id="run_flow",
            step_type="notify",
            message="Run follow-up",
            action=ActionItem(type="run", label="Run flow"),
        )
    )

    result = ProjectNotifyActionUseCase().execute(state=state)

    assert result.state.notify_action is None


def _action_item(*, sequence: int | None = None) -> StepNotifyActionItem:
    return StepNotifyActionItem(
        sequence=sequence,
        run_id="run-1",
        step_id="auth_link",
        step_type="notify",
        message="Authorize the app",
        action=ActionOpenUrlItem(
            type="open_url",
            label="Open authorization",
            message="Open the authorization link.",
            url="https://example.com/oauth/start",
        ),
    )


def _action_item_without_action_message() -> StepNotifyActionItem:
    return StepNotifyActionItem(
        run_id="run-1",
        step_id="auth_link",
        step_type="notify",
        message="Authorize the app",
        action=ActionOpenUrlItem(
            type="open_url",
            label="Open authorization",
            url="https://example.com/oauth/start",
        ),
    )
