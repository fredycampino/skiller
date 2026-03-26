from __future__ import annotations

from io import StringIO

import pytest

from skiller.tools.ui.app import run_ui
from skiller.tools.ui.commands import (
    ClearCommand,
    EchoCommand,
    ExitCommand,
    HelpCommand,
    InputCommand,
    LogsCommand,
    ResumeCommand,
    RunCommand,
    RunsCommand,
    SessionCommand,
    StatusCommand,
    WatchCommand,
    WebhooksCommand,
    parse_command,
)
from skiller.tools.ui.session import build_session_key

pytestmark = pytest.mark.unit


def test_build_session_key_returns_short_token() -> None:
    session_key = build_session_key()

    assert len(session_key) == 8
    assert isinstance(int(session_key, 16), int)


def test_parse_command_returns_echo_for_non_empty_text() -> None:
    command = parse_command("hola\n")

    assert command == EchoCommand(message="hola")


def test_parse_command_returns_exit_for_exit_keyword() -> None:
    command = parse_command(" exit \n")

    assert command == ExitCommand()


def test_parse_command_returns_help_for_help_command() -> None:
    command = parse_command("/help\n")

    assert command == HelpCommand()


def test_parse_command_returns_session_for_session_command() -> None:
    command = parse_command("/session\n")

    assert command == SessionCommand()


def test_parse_command_returns_runs_for_runs_command() -> None:
    command = parse_command("/runs\n")

    assert command == RunsCommand(statuses=[])


def test_parse_command_returns_runs_with_status_filter() -> None:
    command = parse_command("/runs --status WAITING\n")

    assert command == RunsCommand(statuses=["WAITING"])


def test_parse_command_returns_webhooks_command() -> None:
    command = parse_command("/webhooks\n")

    assert command == WebhooksCommand()


def test_parse_command_returns_clear_for_clear_command() -> None:
    command = parse_command("/clear\n")

    assert command == ClearCommand()


def test_parse_command_returns_clear_for_clean_alias() -> None:
    command = parse_command("/clean\n")

    assert command == ClearCommand()


def test_parse_command_returns_run_command_for_run_prefix() -> None:
    command = parse_command("/run notify_test --arg foo=bar\n")

    assert command == RunCommand(raw_args="notify_test --arg foo=bar")


def test_parse_command_returns_status_command() -> None:
    command = parse_command("/status run-1\n")

    assert command == StatusCommand(run_id="run-1")


def test_parse_command_returns_logs_command() -> None:
    command = parse_command("/logs run-1\n")

    assert command == LogsCommand(run_id="run-1")


def test_parse_command_returns_watch_command() -> None:
    command = parse_command("/watch run-1\n")

    assert command == WatchCommand(run_id="run-1")


def test_parse_command_returns_resume_command() -> None:
    command = parse_command("/resume run-1\n")

    assert command == ResumeCommand(run_id="run-1")


def test_parse_command_returns_input_command() -> None:
    command = parse_command("/input run-1 hola mundo\n")

    assert command == InputCommand(run_id="run-1", text="hola mundo")


def test_run_ui_handles_commands_and_echo_until_exit() -> None:
    stdin = StringIO("hola\n/help\n/session\n/clear\n/run notify_test\n/session\nexit\n")
    stdout = StringIO()

    class _FakeRuntimeAdapter:
        def run(self, *, raw_args: str) -> dict[str, str]:
            assert raw_args == "notify_test"
            return {
                "run_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "SUCCEEDED",
            }

    session_key = run_ui(
        stdin=stdin,
        stdout=stdout,
        session_key="a1b2c3d4",
        runtime_adapter=_FakeRuntimeAdapter(),
    )

    assert session_key == "a1b2c3d4"
    assert stdout.getvalue() == (
        "session_key: a1b2c3d4\n"
        "Type a message and press Enter. Type 'exit' to quit.\n"
        "> [a1b2c3d4] echo: hola\n"
        "> Commands:\n"
        "  /help                      Show this help\n"
        "  /session                   Show known runs and current selection\n"
        "  /runs                      Show recent persisted runs\n"
        "  /webhooks                  Show registered webhook channels\n"
        "  /clear                     Clear the screen\n"
        "  /run <args>                Run a skill, for example: /run notify_test\n"
        "  /run --file <path>         Run a skill file, for example: "
        "/run --file skill.yaml\n"
        "  /status <run_id>           Show run status\n"
        "  /logs <run_id>             Show recent run logs\n"
        "  /watch <run_id>            Watch a run until it stops\n"
        "  /input <run_id> <text>     Send text to a waiting input step\n"
        "  /resume <run_id>           Resume a waiting run\n"
        "  /exit                      Exit the UI\n"
        "> session_key: a1b2c3d4\n"
        "selected_run_id: -\n"
        "last_run_id: -\n"
        "runs: []\n"
        "> \033[2J\033[H"
        "> run_id: 550e8400-e29b-41d4-a716-446655440000 status: SUCCEEDED args: notify_test\n"
        "> session_key: a1b2c3d4\n"
        "selected_run_id: 550e8400-e29b-41d4-a716-446655440000\n"
        "last_run_id: 550e8400-e29b-41d4-a716-446655440000\n"
        "runs[1]: 550e8400-e29b-41d4-a716-446655440000 SUCCEEDED * notify_test\n"
        "selected: run_id: 550e8400-e29b-41d4-a716-446655440000 "
        "status: SUCCEEDED args: notify_test\n"
        'last_payload: {"run_id": "550e8400-e29b-41d4-a716-446655440000", '
        '"status": "SUCCEEDED"}\n'
        "> bye\n"
    )


def test_run_ui_records_failed_run_when_runtime_command_errors() -> None:
    stdin = StringIO("/run\n/session\nexit\n")
    stdout = StringIO()

    class _FakeRuntimeAdapter:
        def run(self, *, raw_args: str) -> dict[str, str]:
            raise RuntimeError("run command requires skill args, for example: /run notify_test")

    run_ui(
        stdin=stdin,
        stdout=stdout,
        session_key="a1b2c3d4",
        runtime_adapter=_FakeRuntimeAdapter(),
    )

    assert stdout.getvalue() == (
        "session_key: a1b2c3d4\n"
        "Type a message and press Enter. Type 'exit' to quit.\n"
        "> run_id: - status: FAILED args: <empty>\n"
        "error: run command requires skill args, for example: /run notify_test\n"
        "> session_key: a1b2c3d4\n"
        "selected_run_id: -\n"
        "last_run_id: -\n"
        "runs[1]: - "
        "FAILED <empty> error=run command requires skill args, "
        "for example: /run notify_test\n"
        "> bye\n"
    )


def test_run_ui_supports_waiting_input_watch_flow() -> None:
    stdin = StringIO("/run notify_test\n/input run-1 hola\n/watch run-1\n/session\nexit\n")
    stdout = StringIO()

    class _FakeRuntimeAdapter:
        def run(self, *, raw_args: str) -> dict[str, str]:
            assert raw_args == "notify_test"
            return {"run_id": "run-1", "status": "WAITING"}

        def status(self, *, run_id: str) -> dict[str, str]:
            raise AssertionError("not expected")

        def logs(self, *, run_id: str) -> list[dict[str, object]]:
            raise AssertionError("not expected")

        def watch(self, *, run_id: str) -> dict[str, str]:
            assert run_id == "run-1"
            return {
                "run_id": "run-1",
                "status": "SUCCEEDED",
                "events_text": '[1234] NOTIFY step="done"',
            }

        def input_receive(self, *, run_id: str, text: str) -> dict[str, object]:
            assert run_id == "run-1"
            assert text == "hola"
            return {"accepted": True, "matched_runs": ["run-1"]}

        def resume(self, *, run_id: str) -> dict[str, object]:
            raise AssertionError("not expected")

    run_ui(
        stdin=stdin,
        stdout=stdout,
        session_key="a1b2c3d4",
        runtime_adapter=_FakeRuntimeAdapter(),
    )

    assert stdout.getvalue() == (
        "session_key: a1b2c3d4\n"
        "Type a message and press Enter. Type 'exit' to quit.\n"
        "> run_id: run-1 status: WAITING args: notify_test\n"
        "next: /watch run-1\n"
        "> input: run_id: run-1 accepted: True\n"
        'matched_runs: ["run-1"]\n'
        "> watch: run_id: run-1 status: SUCCEEDED\n"
        'events: [1234] NOTIFY step="done"\n'
        "> session_key: a1b2c3d4\n"
        "selected_run_id: run-1\n"
        "last_run_id: run-1\n"
        "runs[1]: run-1 SUCCEEDED * notify_test\n"
        "selected: run_id: run-1 status: SUCCEEDED args: notify_test\n"
        'last_payload: {"events_text": "[1234] NOTIFY step=\\"done\\"", '
        '"run_id": "run-1", "status": "SUCCEEDED"}\n'
        "> bye\n"
    )


def test_run_ui_renders_waiting_input_metadata_from_run_result() -> None:
    stdin = StringIO("/run wait_input_test\nexit\n")
    stdout = StringIO()

    class _FakeRuntimeAdapter:
        def run(self, *, raw_args: str) -> dict[str, str]:
            assert raw_args == "wait_input_test"
            return {
                "run_id": "run-1",
                "status": "WAITING",
                "wait_type": "input",
                "prompt": "Write a short summary",
            }

    run_ui(
        stdin=stdin,
        stdout=stdout,
        session_key="a1b2c3d4",
        runtime_adapter=_FakeRuntimeAdapter(),
    )

    assert stdout.getvalue() == (
        "session_key: a1b2c3d4\n"
        "Type a message and press Enter. Type 'exit' to quit.\n"
        "> run_id: run-1\n"
        "args: wait_input_test\n"
        "status: WAITING input\n"
        "prompt: Write a short summary\n"
        "next: /input run-1 <text>\n"
        "next: /watch run-1\n"
        "> bye\n"
    )


def test_run_ui_renders_waiting_webhook_metadata_from_status() -> None:
    stdin = StringIO("/status run-1\nexit\n")
    stdout = StringIO()

    class _FakeRuntimeAdapter:
        def run(self, *, raw_args: str) -> dict[str, str]:
            raise AssertionError("not expected")

        def runs(self, *, statuses: list[str] | None = None) -> list[dict[str, object]]:
            raise AssertionError("not expected")

        def status(self, *, run_id: str) -> dict[str, str]:
            assert run_id == "run-1"
            return {
                "id": "run-1",
                "skill_ref": "webhook_signal_oracle",
                "status": "WAITING",
                "wait_type": "webhook",
                "webhook": "market-signal",
                "key": "btc-usd",
            }

        def logs(self, *, run_id: str) -> list[dict[str, object]]:
            raise AssertionError("not expected")

        def watch(self, *, run_id: str) -> dict[str, str]:
            raise AssertionError("not expected")

        def input_receive(self, *, run_id: str, text: str) -> dict[str, object]:
            raise AssertionError("not expected")

        def resume(self, *, run_id: str) -> dict[str, object]:
            raise AssertionError("not expected")

    run_ui(
        stdin=stdin,
        stdout=stdout,
        session_key="a1b2c3d4",
        runtime_adapter=_FakeRuntimeAdapter(),
    )

    assert stdout.getvalue() == (
        "session_key: a1b2c3d4\n"
        "Type a message and press Enter. Type 'exit' to quit.\n"
        "> run_id: run-1\n"
        "args: webhook_signal_oracle\n"
        "status: WAITING webhook\n"
        "webhook: market-signal\n"
        "key: btc-usd\n"
        "next: /watch run-1\n"
        "> bye\n"
    )


def test_run_ui_supports_global_runs_listing() -> None:
    stdin = StringIO("/runs\nexit\n")
    stdout = StringIO()

    class _FakeRuntimeAdapter:
        def run(self, *, raw_args: str) -> dict[str, str]:
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

        def status(self, *, run_id: str) -> dict[str, str]:
            raise AssertionError("not expected")

        def logs(self, *, run_id: str) -> list[dict[str, object]]:
            raise AssertionError("not expected")

        def watch(self, *, run_id: str) -> dict[str, str]:
            raise AssertionError("not expected")

        def input_receive(self, *, run_id: str, text: str) -> dict[str, object]:
            raise AssertionError("not expected")

        def resume(self, *, run_id: str) -> dict[str, object]:
            raise AssertionError("not expected")

    run_ui(
        stdin=stdin,
        stdout=stdout,
        session_key="a1b2c3d4",
        runtime_adapter=_FakeRuntimeAdapter(),
    )

    assert stdout.getvalue() == (
        "session_key: a1b2c3d4\n"
        "Type a message and press Enter. Type 'exit' to quit.\n"
        "> runs:\n"
        "  run-1  WAITING  webhook_signal_oracle  start\n"
        "  run-2  SUCCEEDED  wait_input_test  done\n"
        "> bye\n"
    )


def test_run_ui_supports_filtered_global_runs_listing() -> None:
    stdin = StringIO("/runs --status WAITING\nexit\n")
    stdout = StringIO()

    class _FakeRuntimeAdapter:
        def run(self, *, raw_args: str) -> dict[str, str]:
            raise AssertionError("not expected")

        def runs(self, *, statuses: list[str] | None = None) -> list[dict[str, object]]:
            assert statuses == ["WAITING"]
            return [
                {
                    "id": "run-1",
                    "status": "WAITING",
                    "skill_ref": "webhook_signal_oracle",
                    "current": "start",
                }
            ]

        def status(self, *, run_id: str) -> dict[str, str]:
            raise AssertionError("not expected")

        def logs(self, *, run_id: str) -> list[dict[str, object]]:
            raise AssertionError("not expected")

        def watch(self, *, run_id: str) -> dict[str, str]:
            raise AssertionError("not expected")

        def input_receive(self, *, run_id: str, text: str) -> dict[str, object]:
            raise AssertionError("not expected")

        def resume(self, *, run_id: str) -> dict[str, object]:
            raise AssertionError("not expected")

    run_ui(
        stdin=stdin,
        stdout=stdout,
        session_key="a1b2c3d4",
        runtime_adapter=_FakeRuntimeAdapter(),
    )

    assert stdout.getvalue() == (
        "session_key: a1b2c3d4\n"
        "Type a message and press Enter. Type 'exit' to quit.\n"
        "> runs:\n"
        "  run-1  WAITING  webhook_signal_oracle  start\n"
        "> bye\n"
    )


def test_run_ui_supports_webhooks_listing() -> None:
    stdin = StringIO("/webhooks\nexit\n")
    stdout = StringIO()

    class _FakeRuntimeAdapter:
        def run(self, *, raw_args: str) -> dict[str, str]:
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

        def status(self, *, run_id: str) -> dict[str, str]:
            raise AssertionError("not expected")

        def logs(self, *, run_id: str) -> list[dict[str, object]]:
            raise AssertionError("not expected")

        def watch(self, *, run_id: str) -> dict[str, str]:
            raise AssertionError("not expected")

        def input_receive(self, *, run_id: str, text: str) -> dict[str, object]:
            raise AssertionError("not expected")

        def resume(self, *, run_id: str) -> dict[str, object]:
            raise AssertionError("not expected")

    run_ui(
        stdin=stdin,
        stdout=stdout,
        session_key="a1b2c3d4",
        runtime_adapter=_FakeRuntimeAdapter(),
    )

    assert stdout.getvalue() == (
        "session_key: a1b2c3d4\n"
        "Type a message and press Enter. Type 'exit' to quit.\n"
        "> webhooks:\n"
        "  github-ci  enabled=true  created_at=2026-03-19 10:00:00\n"
        "> bye\n"
    )
