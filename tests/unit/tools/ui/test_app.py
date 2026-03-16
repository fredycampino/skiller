from __future__ import annotations

import uuid
from io import StringIO
from unittest.mock import patch

import pytest

from skiller.tools.ui.app import run_ui
from skiller.tools.ui.commands import (
    ClearCommand,
    EchoCommand,
    ExitCommand,
    HelpCommand,
    RunCommand,
    SessionCommand,
    parse_command,
)
from skiller.tools.ui.session import build_run_id, build_session_key

pytestmark = pytest.mark.unit


def test_build_session_key_returns_short_token() -> None:
    session_key = build_session_key()

    assert len(session_key) == 8
    assert isinstance(int(session_key, 16), int)


def test_build_run_id_returns_uuid() -> None:
    run_id = build_run_id()

    assert str(uuid.UUID(run_id)) == run_id


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


def test_parse_command_returns_clear_for_clear_command() -> None:
    command = parse_command("/clear\n")

    assert command == ClearCommand()


def test_parse_command_returns_clear_for_clean_alias() -> None:
    command = parse_command("/clean\n")

    assert command == ClearCommand()


def test_parse_command_returns_run_command_for_run_prefix() -> None:
    command = parse_command("/run notify_test --arg foo=bar\n")

    assert command == RunCommand(raw_args="notify_test --arg foo=bar")


def test_run_ui_handles_commands_and_echo_until_exit() -> None:
    stdin = StringIO("hola\n/help\n/session\n/clear\n/run notify_test\n/session\nexit\n")
    stdout = StringIO()

    with (
        patch(
            "skiller.tools.ui.app.build_run_id",
            return_value="550e8400-e29b-41d4-a716-446655440000",
        ),
        patch(
            "skiller.tools.ui.app.execute_run",
            return_value={
                "run_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "SUCCEEDED",
            },
        ),
    ):
        session_key = run_ui(
            stdin=stdin,
            stdout=stdout,
            session_key="a1b2c3d4",
        )

    assert session_key == "a1b2c3d4"
    assert stdout.getvalue() == (
        "session_key: a1b2c3d4\n"
        "Type a message and press Enter. Type 'exit' to quit.\n"
        "> [a1b2c3d4] echo: hola\n"
        "> Commands: /help, /session, /clear, /run <args>, /exit\n"
        "Tip: /run forwards args to `skiller run`, "
        "including flags like --file and --start-webhooks\n"
        "> session_key: a1b2c3d4\n"
        "runs: []\n"
        "> \033[2J\033[H"
        "> run_id: 550e8400-e29b-41d4-a716-446655440000 status: SUCCEEDED args: notify_test\n"
        "> session_key: a1b2c3d4\n"
        "runs[1]: 550e8400-e29b-41d4-a716-446655440000 SUCCEEDED notify_test\n"
        "> bye\n"
    )


def test_run_ui_records_failed_run_when_runtime_command_errors() -> None:
    stdin = StringIO("/run\n/session\nexit\n")
    stdout = StringIO()

    with (
        patch(
            "skiller.tools.ui.app.build_run_id",
            return_value="550e8400-e29b-41d4-a716-446655440001",
        ),
        patch(
            "skiller.tools.ui.app.execute_run",
            side_effect=RuntimeError(
                "run command requires skill args, for example: /run notify_test"
            ),
        ),
    ):
        run_ui(
            stdin=stdin,
            stdout=stdout,
            session_key="a1b2c3d4",
        )

    assert stdout.getvalue() == (
        "session_key: a1b2c3d4\n"
        "Type a message and press Enter. Type 'exit' to quit.\n"
        "> run_id: 550e8400-e29b-41d4-a716-446655440001 status: FAILED args: <empty>\n"
        "error: run command requires skill args, for example: /run notify_test\n"
        "> session_key: a1b2c3d4\n"
        "runs[1]: 550e8400-e29b-41d4-a716-446655440001 "
        "FAILED <empty> error=run command requires skill args, "
        "for example: /run notify_test\n"
        "> bye\n"
    )
