from __future__ import annotations

import pytest

from skiller.tools.ui.actions import handle_command
from skiller.tools.ui.commands import (
    BodyCommand,
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


def test_succeeded_run_command_loads_logs_for_transcript_rendering() -> None:
    class _FakeRuntimeAdapter:
        def run(self, *, raw_args: str) -> dict[str, object]:
            assert raw_args == "repo_checks"
            return {
                "run_id": "run-1",
                "status": "SUCCEEDED",
            }

        def logs(self, *, run_id: str) -> list[dict[str, object]]:
            assert run_id == "run-1"
            return [
                {"id": "evt-1", "type": "RUN_CREATE", "payload": {"skill_ref": "repo_checks"}},
                {
                    "id": "evt-2",
                    "type": "STEP_SUCCESS",
                    "payload": {
                        "step": "run_ruff",
                        "step_type": "shell",
                        "output": {
                            "text": "All checks passed!",
                            "value": {"ok": True, "exit_code": 0},
                            "body_ref": None,
                        },
                    },
                },
            ]

    session = UiSession(session_key="a1b2c3d4")

    result = handle_command(
        session=session,
        command=RunCommand(raw_args="repo_checks"),
        runtime=_FakeRuntimeAdapter(),
    )

    assert result.kind == "run"
    assert result.run is not None
    assert result.run.run_id == "run-1"
    assert result.run.status == "SUCCEEDED"
    assert result.run.logs == [
        {"id": "evt-1", "type": "RUN_CREATE", "payload": {"skill_ref": "repo_checks"}},
        {
            "id": "evt-2",
            "type": "STEP_SUCCESS",
            "payload": {
                "step": "run_ruff",
                "step_type": "shell",
                "output": {
                    "text": "All checks passed!",
                    "value": {"ok": True, "exit_code": 0},
                    "body_ref": None,
                },
            },
        },
    ]


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
            return [{"id": "evt-1", "type": "STEP_SUCCESS", "payload": {}}]

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
    assert result.logs == [{"id": "evt-1", "type": "STEP_SUCCESS", "payload": {}}]
    assert result.run is not None
    assert result.run.run_id == "run-1"
    assert result.run.logs == [{"id": "evt-1", "type": "STEP_SUCCESS", "payload": {}}]


def test_logs_command_uses_selected_run_when_run_id_is_missing() -> None:
    class _FakeRuntimeAdapter:
        def run(self, *, raw_args: str) -> dict[str, object]:
            raise AssertionError("not expected")

        def runs(self, *, statuses: list[str] | None = None) -> list[dict[str, object]]:
            _ = statuses
            raise AssertionError("not expected")

        def status(self, *, run_id: str) -> dict[str, object]:
            raise AssertionError("not expected")

        def logs(self, *, run_id: str) -> list[dict[str, object]]:
            assert run_id == "run-2"
            return [{"id": "evt-1", "type": "STEP_SUCCESS", "payload": {}}]

        def watch(self, *, run_id: str) -> dict[str, object]:
            raise AssertionError("not expected")

        def input_receive(self, *, run_id: str, text: str) -> dict[str, object]:
            raise AssertionError("not expected")

        def resume(self, *, run_id: str) -> dict[str, object]:
            raise AssertionError("not expected")

    session = UiSession(session_key="a1b2c3d4")
    session.ensure_run("run-1", raw_args="notify_test")
    selected_run = session.ensure_run("run-2", raw_args="chat")
    session.selected_run_id = "run-2"
    session.last_run_id = "run-1"

    result = handle_command(
        session=session,
        command=LogsCommand(run_id=""),
        runtime=_FakeRuntimeAdapter(),
    )

    assert result.kind == "logs"
    assert result.run is selected_run
    assert result.logs == [{"id": "evt-1", "type": "STEP_SUCCESS", "payload": {}}]


def test_logs_command_uses_last_run_when_selected_run_is_missing() -> None:
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
            return [{"id": "evt-1", "type": "STEP_SUCCESS", "payload": {}}]

        def watch(self, *, run_id: str) -> dict[str, object]:
            raise AssertionError("not expected")

        def input_receive(self, *, run_id: str, text: str) -> dict[str, object]:
            raise AssertionError("not expected")

        def resume(self, *, run_id: str) -> dict[str, object]:
            raise AssertionError("not expected")

    session = UiSession(session_key="a1b2c3d4")
    last_run = session.ensure_run("run-1", raw_args="notify_test")
    session.last_run_id = "run-1"

    result = handle_command(
        session=session,
        command=LogsCommand(run_id=""),
        runtime=_FakeRuntimeAdapter(),
    )

    assert result.kind == "logs"
    assert result.run is last_run
    assert result.logs == [{"id": "evt-1", "type": "STEP_SUCCESS", "payload": {}}]


def test_logs_command_resolves_llm_prompt_body_ref_for_ui() -> None:
    class _FakeRuntimeAdapter:
        def run(self, *, raw_args: str) -> dict[str, object]:
            raise AssertionError("not expected")

        def runs(self, *, statuses: list[str] | None = None) -> list[dict[str, object]]:
            _ = statuses
            raise AssertionError("not expected")

        def webhooks(self) -> list[dict[str, object]]:
            raise AssertionError("not expected")

        def status(self, *, run_id: str) -> dict[str, object]:
            raise AssertionError("not expected")

        def logs(self, *, run_id: str) -> list[dict[str, object]]:
            assert run_id == "run-1"
            return [
                {
                    "id": "evt-1",
                    "type": "STEP_SUCCESS",
                    "payload": {
                        "step": "answer",
                        "step_type": "llm_prompt",
                        "output": {
                            "text": "preview...",
                            "text_ref": "data.reply",
                            "value": {"data": {"truncated": True, "reply": "preview..."}},
                            "body_ref": "execution_output:1",
                        },
                    },
                }
            ]

        def get_execution_output(self, *, body_ref: str) -> dict[str, object] | None:
            assert body_ref == "execution_output:1"
            return {
                "value": {"data": {"reply": "respuesta completa"}},
            }

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
    assert result.logs == [
        {
            "id": "evt-1",
            "type": "STEP_SUCCESS",
            "payload": {
                "step": "answer",
                "step_type": "llm_prompt",
                "output": {
                    "text": "respuesta completa",
                    "text_ref": "data.reply",
                    "value": {"data": {"reply": "respuesta completa"}},
                    "body_ref": "execution_output:1",
                },
            },
        }
    ]


def test_body_command_returns_output_body_payload() -> None:
    class _FakeRuntimeAdapter:
        def run(self, *, raw_args: str) -> dict[str, object]:
            raise AssertionError("not expected")

        def runs(self, *, statuses: list[str] | None = None) -> list[dict[str, object]]:
            _ = statuses
            raise AssertionError("not expected")

        def webhooks(self) -> list[dict[str, object]]:
            raise AssertionError("not expected")

        def status(self, *, run_id: str) -> dict[str, object]:
            raise AssertionError("not expected")

        def logs(self, *, run_id: str) -> list[dict[str, object]]:
            raise AssertionError("not expected")

        def get_execution_output(self, *, body_ref: str) -> dict[str, object] | None:
            assert body_ref == "execution_output:1"
            return {"data": {"reply": "hola"}}

        def watch(self, *, run_id: str) -> dict[str, object]:
            raise AssertionError("not expected")

        def input_receive(self, *, run_id: str, text: str) -> dict[str, object]:
            raise AssertionError("not expected")

        def resume(self, *, run_id: str) -> dict[str, object]:
            raise AssertionError("not expected")

    result = handle_command(
        session=UiSession(session_key="a1b2c3d4"),
        command=BodyCommand(body_ref="execution_output:1"),
        runtime=_FakeRuntimeAdapter(),
    )

    assert result.kind == "body"
    assert result.body_ref == "execution_output:1"
    assert result.payload == {"data": {"reply": "hola"}}


def test_status_command_resolves_llm_prompt_body_ref_in_context() -> None:
    class _FakeRuntimeAdapter:
        def run(self, *, raw_args: str) -> dict[str, object]:
            raise AssertionError("not expected")

        def runs(self, *, statuses: list[str] | None = None) -> list[dict[str, object]]:
            _ = statuses
            raise AssertionError("not expected")

        def webhooks(self) -> list[dict[str, object]]:
            raise AssertionError("not expected")

        def status(self, *, run_id: str) -> dict[str, object]:
            assert run_id == "run-1"
            return {
                "id": "run-1",
                "status": "WAITING",
                "skill_ref": "chat",
                "context": {
                    "inputs": {},
                    "step_executions": {
                        "answer": {
                            "step_type": "llm_prompt",
                            "input": {},
                            "evaluation": {},
                            "output": {
                                "text": "preview...",
                                "text_ref": "data.reply",
                                "value": {"data": {"truncated": True, "reply": "preview..."}},
                                "body_ref": "execution_output:1",
                            },
                        }
                    },
                },
            }

        def logs(self, *, run_id: str) -> list[dict[str, object]]:
            raise AssertionError("not expected")

        def get_execution_output(self, *, body_ref: str) -> dict[str, object] | None:
            assert body_ref == "execution_output:1"
            return {
                "value": {"data": {"reply": "respuesta completa"}},
            }

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
        "skill_ref": "chat",
        "context": {
            "inputs": {},
            "step_executions": {
                "answer": {
                    "step_type": "llm_prompt",
                    "input": {},
                    "evaluation": {},
                    "output": {
                        "text": "respuesta completa",
                        "text_ref": "data.reply",
                        "value": {"data": {"reply": "respuesta completa"}},
                        "body_ref": "execution_output:1",
                    },
                }
            },
        },
    }


def test_body_command_returns_error_when_body_ref_is_missing() -> None:
    class _FakeRuntimeAdapter:
        def run(self, *, raw_args: str) -> dict[str, object]:
            raise AssertionError("not expected")

        def runs(self, *, statuses: list[str] | None = None) -> list[dict[str, object]]:
            _ = statuses
            raise AssertionError("not expected")

        def webhooks(self) -> list[dict[str, object]]:
            raise AssertionError("not expected")

        def status(self, *, run_id: str) -> dict[str, object]:
            raise AssertionError("not expected")

        def logs(self, *, run_id: str) -> list[dict[str, object]]:
            raise AssertionError("not expected")

        def get_execution_output(self, *, body_ref: str) -> dict[str, object] | None:
            raise AssertionError("not expected")

        def watch(self, *, run_id: str) -> dict[str, object]:
            raise AssertionError("not expected")

        def input_receive(self, *, run_id: str, text: str) -> dict[str, object]:
            raise AssertionError("not expected")

        def resume(self, *, run_id: str) -> dict[str, object]:
            raise AssertionError("not expected")

    result = handle_command(
        session=UiSession(session_key="a1b2c3d4"),
        command=BodyCommand(body_ref=""),
        runtime=_FakeRuntimeAdapter(),
    )

    assert result.kind == "body"
    assert result.run is not None
    assert result.run.error == "body_ref is required for /body"


def test_logs_command_returns_error_when_no_selected_or_last_run_exists() -> None:
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
            raise AssertionError("not expected")

        def resume(self, *, run_id: str) -> dict[str, object]:
            raise AssertionError("not expected")

    result = handle_command(
        session=UiSession(session_key="a1b2c3d4"),
        command=LogsCommand(run_id=""),
        runtime=_FakeRuntimeAdapter(),
    )

    assert result.kind == "logs"
    assert result.logs == []
    assert result.run is not None
    assert result.run.status == "FAILED"
    assert result.run.error == "No selected or last run is available for /logs"


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
                "events": [
                    {
                        "id": "evt-1",
                        "type": "STEP_SUCCESS",
                        "payload": {
                            "step": "done",
                            "step_type": "notify",
                            "output": {
                                "text": "done",
                                "value": {"message": "done"},
                                "body_ref": None,
                            },
                        },
                    }
                ],
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
        "events": [
            {
                "id": "evt-1",
                "type": "STEP_SUCCESS",
                "payload": {
                    "step": "done",
                    "step_type": "notify",
                    "output": {
                        "text": "done",
                        "value": {"message": "done"},
                        "body_ref": None,
                    },
                },
            }
        ],
    }
    assert result.run is run
    assert run.status == "SUCCEEDED"
    assert run.last_payload == {
        "run_id": "run-1",
        "status": "SUCCEEDED",
        "events": [
            {
                "id": "evt-1",
                "type": "STEP_SUCCESS",
                "payload": {
                    "step": "done",
                    "step_type": "notify",
                    "output": {
                        "text": "done",
                        "value": {"message": "done"},
                        "body_ref": None,
                    },
                },
            }
        ],
    }
    assert session.selected_run_id == "run-1"
    assert session.last_run_id == "run-1"
    assert run.seen_event_ids == {"evt-1"}


def test_watch_command_filters_events_already_seen_in_run() -> None:
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
                "status": "WAITING",
                "events": [
                    {
                        "id": "evt-1",
                        "type": "RUN_WAITING",
                        "payload": {
                            "step": "ask_user",
                            "step_type": "wait_input",
                            "output": {"text": "old", "value": {"prompt": "old"}, "body_ref": None},
                        },
                    },
                    {
                        "id": "evt-2",
                        "type": "STEP_SUCCESS",
                        "payload": {
                            "step": "done",
                            "step_type": "notify",
                            "output": {
                                "text": "new",
                                "value": {"message": "new"},
                                "body_ref": None,
                            },
                        },
                    },
                ],
            }

        def input_receive(self, *, run_id: str, text: str) -> dict[str, object]:
            raise AssertionError("not expected")

        def resume(self, *, run_id: str) -> dict[str, object]:
            raise AssertionError("not expected")

    session = UiSession(session_key="a1b2c3d4")
    run = session.ensure_run("run-1", raw_args="chat")
    run.seen_event_ids.add("evt-1")

    result = handle_command(
        session=session,
        command=WatchCommand(run_id="run-1"),
        runtime=_FakeRuntimeAdapter(),
    )

    assert result.payload == {
        "run_id": "run-1",
        "status": "WAITING",
        "events": [
            {
                "id": "evt-2",
                "type": "STEP_SUCCESS",
                "payload": {
                    "step": "done",
                    "step_type": "notify",
                    "output": {"text": "new", "value": {"message": "new"}, "body_ref": None},
                },
            }
        ],
    }
    assert run.seen_event_ids == {"evt-1", "evt-2"}


def test_watch_command_skips_run_create_when_create_block_was_already_rendered() -> None:
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
                "status": "WAITING",
                "events": [
                    {
                        "id": "evt-1",
                        "type": "RUN_CREATE",
                        "payload": {"skill": "chat", "skill_source": "internal"},
                    },
                    {
                        "id": "evt-2",
                        "type": "STEP_SUCCESS",
                        "payload": {
                            "step": "decide_exit",
                            "step_type": "switch",
                            "output": {
                                "text": "answer",
                                "value": {"next_step_id": "answer"},
                                "body_ref": None,
                            },
                        },
                    },
                ],
            }

        def input_receive(self, *, run_id: str, text: str) -> dict[str, object]:
            raise AssertionError("not expected")

        def resume(self, *, run_id: str) -> dict[str, object]:
            raise AssertionError("not expected")

    session = UiSession(session_key="a1b2c3d4")
    run = session.ensure_run("run-1", raw_args="chat")
    run.has_rendered_create_block = True

    result = handle_command(
        session=session,
        command=WatchCommand(run_id="run-1"),
        runtime=_FakeRuntimeAdapter(),
    )

    assert result.payload == {
        "run_id": "run-1",
        "status": "WAITING",
        "events": [
            {
                "id": "evt-2",
                "type": "STEP_SUCCESS",
                "payload": {
                    "step": "decide_exit",
                    "step_type": "switch",
                    "output": {
                        "text": "answer",
                        "value": {"next_step_id": "answer"},
                        "body_ref": None,
                    },
                },
            }
        ],
    }
    assert run.seen_event_ids == {"evt-1", "evt-2"}


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
                    "current": "wait_signal",
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
