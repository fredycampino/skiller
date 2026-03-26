from __future__ import annotations

import pytest

from skiller.tools.ui.actions import handle_command
from skiller.tools.ui.commands import (
    InputCommand,
    LogsCommand,
    RunCommand,
    RunsCommand,
    StatusCommand,
    WatchCommand,
    WebhooksCommand,
)
from skiller.tools.ui.session import UiSession

pytestmark = pytest.mark.unit


def test_run_command_updates_session_selection_and_payload() -> None:
    class _FakeRuntimeAdapter:
        def run(self, *, raw_args: str) -> dict[str, object]:
            assert raw_args == "notify_test"
            return {
                "run_id": "run-1",
                "status": "WAITING",
                "webhooks_started": False,
            }

    session = UiSession(session_key="a1b2c3d4")

    result = handle_command(
        session=session,
        command=RunCommand(raw_args="notify_test"),
        runtime=_FakeRuntimeAdapter(),
    )

    assert result.kind == "run"
    assert result.run is not None
    assert result.run.run_id == "run-1"
    assert result.run.status == "WAITING"
    assert result.run.last_payload == {
        "run_id": "run-1",
        "status": "WAITING",
        "webhooks_started": False,
    }
    assert result.run.logs == []
    assert session.selected_run_id == "run-1"
    assert session.last_run_id == "run-1"


def test_failed_run_does_not_update_selected_or_last_run() -> None:
    class _FakeRuntimeAdapter:
        def run(self, *, raw_args: str) -> dict[str, object]:
            raise RuntimeError("boom")

    session = UiSession(session_key="a1b2c3d4")

    result = handle_command(
        session=session,
        command=RunCommand(raw_args="notify_test"),
        runtime=_FakeRuntimeAdapter(),
    )

    assert result.kind == "run"
    assert result.run is not None
    assert result.run.run_id is None
    assert result.run.status == "FAILED"
    assert session.selected_run_id is None
    assert session.last_run_id is None


def test_status_command_returns_payload() -> None:
    class _FakeRuntimeAdapter:
        def run(self, *, raw_args: str) -> dict[str, object]:
            raise AssertionError("not expected")

        def runs(self, *, statuses: list[str] | None = None) -> list[dict[str, object]]:
            _ = statuses
            raise AssertionError("not expected")

        def status(self, *, run_id: str) -> dict[str, object]:
            assert run_id == "run-1"
            return {"id": "run-1", "status": "WAITING", "skill_ref": "wait_input_test"}

        def logs(self, *, run_id: str) -> list[dict[str, object]]:
            raise AssertionError("not expected")

        def watch(self, *, run_id: str) -> dict[str, object]:
            raise AssertionError("not expected")

        def input_receive(self, *, run_id: str, text: str) -> dict[str, object]:
            raise AssertionError("not expected")

        def resume(self, *, run_id: str) -> dict[str, object]:
            raise AssertionError("not expected")

    result = handle_command(
        session=UiSession(session_key="a1b2c3d4"),
        command=StatusCommand(run_id="run-1"),
        runtime=_FakeRuntimeAdapter(),
    )

    assert result.kind == "status"
    assert result.payload == {
        "id": "run-1",
        "status": "WAITING",
        "skill_ref": "wait_input_test",
    }
    assert result.run is not None
    assert result.run.run_id == "run-1"
    assert result.run.raw_args == "wait_input_test"
    assert result.run.status == "WAITING"
    assert result.run.last_payload == {
        "id": "run-1",
        "status": "WAITING",
        "skill_ref": "wait_input_test",
    }
    assert result.run.logs == []


def test_logs_command_returns_log_list() -> None:
    class _FakeRuntimeAdapter:
        def run(self, *, raw_args: str) -> dict[str, object]:
            raise AssertionError("not expected")

        def runs(self, *, statuses: list[str] | None = None) -> list[dict[str, object]]:
            _ = statuses
            raise AssertionError("not expected")

        def status(self, *, run_id: str) -> dict[str, object]:
            raise AssertionError("not expected")

        def logs(self, *, run_id: str) -> list[dict[str, object]]:
            assert run_id == "run-1"
            return [{"id": "evt-1", "type": "NOTIFY", "payload": {}}]

        def watch(self, *, run_id: str) -> dict[str, object]:
            raise AssertionError("not expected")

        def input_receive(self, *, run_id: str, text: str) -> dict[str, object]:
            raise AssertionError("not expected")

        def resume(self, *, run_id: str) -> dict[str, object]:
            raise AssertionError("not expected")

    result = handle_command(
        session=UiSession(session_key="a1b2c3d4"),
        command=LogsCommand(run_id="run-1"),
        runtime=_FakeRuntimeAdapter(),
    )

    assert result.kind == "logs"
    assert result.logs == [{"id": "evt-1", "type": "NOTIFY", "payload": {}}]
    assert result.run is not None
    assert result.run.run_id == "run-1"
    assert result.run.logs == [{"id": "evt-1", "type": "NOTIFY", "payload": {}}]


def test_input_command_returns_payload() -> None:
    class _FakeRuntimeAdapter:
        def run(self, *, raw_args: str) -> dict[str, object]:
            raise AssertionError("not expected")

        def runs(self, *, statuses: list[str] | None = None) -> list[dict[str, object]]:
            _ = statuses
            raise AssertionError("not expected")

        def status(self, *, run_id: str) -> dict[str, object]:
            raise AssertionError("not expected")

        def logs(self, *, run_id: str) -> list[dict[str, object]]:
            raise AssertionError("not expected")

        def watch(self, *, run_id: str) -> dict[str, object]:
            raise AssertionError("not expected")

        def input_receive(self, *, run_id: str, text: str) -> dict[str, object]:
            assert run_id == "run-1"
            assert text == "hola"
            return {"accepted": True, "matched_runs": ["run-1"]}

        def resume(self, *, run_id: str) -> dict[str, object]:
            raise AssertionError("not expected")

    result = handle_command(
        session=UiSession(session_key="a1b2c3d4"),
        command=InputCommand(run_id="run-1", text="hola"),
        runtime=_FakeRuntimeAdapter(),
    )

    assert result.kind == "input"
    assert result.payload == {"accepted": True, "matched_runs": ["run-1"]}
    assert result.run is not None
    assert result.run.run_id == "run-1"


def test_watch_command_updates_existing_run_to_succeeded() -> None:
    class _FakeRuntimeAdapter:
        def run(self, *, raw_args: str) -> dict[str, object]:
            raise AssertionError("not expected")

        def runs(self, *, statuses: list[str] | None = None) -> list[dict[str, object]]:
            _ = statuses
            raise AssertionError("not expected")

        def status(self, *, run_id: str) -> dict[str, object]:
            raise AssertionError("not expected")

        def logs(self, *, run_id: str) -> list[dict[str, object]]:
            raise AssertionError("not expected")

        def watch(self, *, run_id: str) -> dict[str, object]:
            assert run_id == "run-1"
            return {
                "run_id": "run-1",
                "status": "SUCCEEDED",
                "events_text": '[1234] NOTIFY step="done"',
            }

        def input_receive(self, *, run_id: str, text: str) -> dict[str, object]:
            raise AssertionError("not expected")

        def resume(self, *, run_id: str) -> dict[str, object]:
            raise AssertionError("not expected")

    session = UiSession(session_key="a1b2c3d4")
    run = session.ensure_run("run-1", raw_args="notify_test")
    run.status = "WAITING"

    result = handle_command(
        session=session,
        command=WatchCommand(run_id="run-1"),
        runtime=_FakeRuntimeAdapter(),
    )

    assert result.kind == "watch"
    assert result.payload == {
        "run_id": "run-1",
        "status": "SUCCEEDED",
        "events_text": '[1234] NOTIFY step="done"',
    }
    assert result.run is run
    assert run.status == "SUCCEEDED"
    assert run.last_payload == {
        "run_id": "run-1",
        "status": "SUCCEEDED",
        "events_text": '[1234] NOTIFY step="done"',
    }
    assert session.selected_run_id == "run-1"
    assert session.last_run_id == "run-1"


def test_runs_command_updates_session_with_global_runs() -> None:
    class _FakeRuntimeAdapter:
        def run(self, *, raw_args: str) -> dict[str, object]:
            raise AssertionError("not expected")

        def runs(self, *, statuses: list[str] | None = None) -> list[dict[str, object]]:
            assert statuses == []
            return [
                {
                    "id": "run-1",
                    "status": "WAITING",
                    "skill_ref": "webhook_signal_oracle",
                    "current": "start",
                },
                {
                    "id": "run-2",
                    "status": "SUCCEEDED",
                    "skill_ref": "wait_input_test",
                    "current": "done",
                },
            ]

        def status(self, *, run_id: str) -> dict[str, object]:
            raise AssertionError("not expected")

        def logs(self, *, run_id: str) -> list[dict[str, object]]:
            raise AssertionError("not expected")

        def watch(self, *, run_id: str) -> dict[str, object]:
            raise AssertionError("not expected")

        def input_receive(self, *, run_id: str, text: str) -> dict[str, object]:
            raise AssertionError("not expected")

        def resume(self, *, run_id: str) -> dict[str, object]:
            raise AssertionError("not expected")

    session = UiSession(session_key="a1b2c3d4")

    result = handle_command(
        session=session,
        command=RunsCommand(statuses=[]),
        runtime=_FakeRuntimeAdapter(),
    )

    assert result.kind == "runs"
    assert result.runs is not None
    assert len(result.runs) == 2
    assert [run.run_id for run in session.runs] == ["run-1", "run-2"]
    assert session.runs[0].raw_args == "webhook_signal_oracle"
    assert session.runs[1].status == "SUCCEEDED"


def test_webhooks_command_returns_registry_list() -> None:
    class _FakeRuntimeAdapter:
        def run(self, *, raw_args: str) -> dict[str, object]:
            raise AssertionError("not expected")

        def runs(self, *, statuses: list[str] | None = None) -> list[dict[str, object]]:
            raise AssertionError("not expected")

        def webhooks(self) -> list[dict[str, object]]:
            return [
                {
                    "webhook": "github-ci",
                    "enabled": True,
                    "created_at": "2026-03-19 10:00:00",
                }
            ]

        def status(self, *, run_id: str) -> dict[str, object]:
            raise AssertionError("not expected")

        def logs(self, *, run_id: str) -> list[dict[str, object]]:
            raise AssertionError("not expected")

        def watch(self, *, run_id: str) -> dict[str, object]:
            raise AssertionError("not expected")

        def input_receive(self, *, run_id: str, text: str) -> dict[str, object]:
            raise AssertionError("not expected")

        def resume(self, *, run_id: str) -> dict[str, object]:
            raise AssertionError("not expected")

    result = handle_command(
        session=UiSession(session_key="a1b2c3d4"),
        command=WebhooksCommand(),
        runtime=_FakeRuntimeAdapter(),
    )

    assert result.kind == "webhooks"
    assert result.webhooks == [
        {
            "webhook": "github-ci",
            "enabled": True,
            "created_at": "2026-03-19 10:00:00",
        }
    ]


def test_runs_command_passes_status_filters() -> None:
    class _FakeRuntimeAdapter:
        def run(self, *, raw_args: str) -> dict[str, object]:
            raise AssertionError("not expected")

        def runs(self, *, statuses: list[str] | None = None) -> list[dict[str, object]]:
            assert statuses == ["WAITING"]
            return []

        def status(self, *, run_id: str) -> dict[str, object]:
            raise AssertionError("not expected")

        def logs(self, *, run_id: str) -> list[dict[str, object]]:
            raise AssertionError("not expected")

        def watch(self, *, run_id: str) -> dict[str, object]:
            raise AssertionError("not expected")

        def input_receive(self, *, run_id: str, text: str) -> dict[str, object]:
            raise AssertionError("not expected")

        def resume(self, *, run_id: str) -> dict[str, object]:
            raise AssertionError("not expected")

    result = handle_command(
        session=UiSession(session_key="a1b2c3d4"),
        command=RunsCommand(statuses=["waiting"]),
        runtime=_FakeRuntimeAdapter(),
    )

    assert result.kind == "runs"
    assert result.runs == []
