import pytest

from skiller.application.action.action_mapper import ActionMapper
from skiller.application.action.action_uid_factory import ActionUidFactory
from skiller.domain.action.action_model import OpenUrlAction, RunAction

pytestmark = pytest.mark.unit


class _FakeActionUidFactory(ActionUidFactory):
    def __init__(self, *uids: str) -> None:
        self.uids = list(uids)

    def new_uid(self) -> str:
        return self.uids.pop(0)


def test_action_mapper_builds_notify_open_url_action() -> None:
    action = ActionMapper(_FakeActionUidFactory("action-1")).to_notify_action(
        step_id="auth_link",
        value={
            "type": "open_url",
            "label": "Open authorization",
            "message": "Continue in the browser.",
            "url": "https://example.com/oauth/start",
            "auto": True,
        },
        default_message="Authorize the app",
    )

    assert action == OpenUrlAction(
        uid="action-1",
        label="Open authorization",
        message="Continue in the browser.",
        url="https://example.com/oauth/start",
        auto=True,
    )


def test_action_mapper_defaults_open_url_message_to_notify_message() -> None:
    action = ActionMapper(_FakeActionUidFactory("action-2")).to_notify_action(
        step_id="auth_link",
        value={
            "type": "open_url",
            "label": "Open authorization",
            "url": "https://example.com/oauth/start",
        },
        default_message="Authorize the app",
    )

    assert action == OpenUrlAction(
        uid="action-2",
        label="Open authorization",
        message="Authorize the app",
        url="https://example.com/oauth/start",
        auto=False,
    )


def test_action_mapper_returns_none_when_notify_action_is_missing() -> None:
    action = ActionMapper(_FakeActionUidFactory()).to_notify_action(
        step_id="show_message",
        value=None,
        default_message="Done",
    )

    assert action is None


def test_action_mapper_builds_notify_run_action() -> None:
    action = ActionMapper(_FakeActionUidFactory("action-3")).to_notify_action(
        step_id="run_followup",
        value={
            "type": "run",
            "label": "Run follow-up",
            "arg": "ci_agent",
            "params": "--source stui",
            "auto": True,
        },
        default_message="Run follow-up",
    )

    assert action == RunAction(
        uid="action-3",
        label="Run follow-up",
        arg="ci_agent",
        params="--source stui",
        auto=True,
    )


def test_action_mapper_rejects_run_action_without_arg() -> None:
    with pytest.raises(ValueError, match="run action requires non-empty arg"):
        ActionMapper(_FakeActionUidFactory()).to_notify_action(
            step_id="run_followup",
            value={
                "type": "run",
                "label": "Run follow-up",
                "arg": "   ",
            },
            default_message="Run follow-up",
        )


def test_action_mapper_rejects_unsupported_notify_action_type() -> None:
    with pytest.raises(ValueError, match="action type must be 'open_url' or 'run'"):
        ActionMapper(_FakeActionUidFactory()).to_notify_action(
            step_id="run_followup",
            value={
                "type": "unknown",
                "label": "Run follow-up",
            },
            default_message="Run follow-up",
        )
