from __future__ import annotations

import pytest

import skiller.tools.ui.app as ui_app
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


def test_parse_command_returns_logs_command_without_run_id() -> None:
    command = parse_command("/logs\n")

    assert command == LogsCommand(run_id="")


def test_parse_command_returns_watch_command() -> None:
    command = parse_command("/watch run-1\n")

    assert command == WatchCommand(run_id="run-1")


def test_parse_command_returns_resume_command() -> None:
    command = parse_command("/resume run-1\n")

    assert command == ResumeCommand(run_id="run-1")


def test_parse_command_returns_input_command() -> None:
    command = parse_command("/input run-1 hola mundo\n")

    assert command == InputCommand(run_id="run-1", text="hola mundo")


def test_run_ui_uses_prompt_toolkit_runner_when_available() -> None:
    recorded: dict[str, object] = {}

    def fake_prompt_toolkit_runner(*, session_key: str | None, runtime_adapter: object) -> str:
        recorded["session_key"] = session_key
        recorded["runtime_adapter"] = runtime_adapter
        return "pt-session"

    session_key = run_ui(
        session_key="a1b2c3d4",
        prompt_toolkit_runner=fake_prompt_toolkit_runner,
    )

    assert session_key == "pt-session"
    assert recorded["session_key"] == "a1b2c3d4"
    assert recorded["runtime_adapter"] is not None


def test_run_ui_loads_prompt_toolkit_runner_when_not_injected() -> None:
    recorded: dict[str, object] = {}
    original_loader = ui_app._load_prompt_toolkit_runner

    def fake_prompt_toolkit_runner(*, session_key: str | None, runtime_adapter: object) -> str:
        recorded["session_key"] = session_key
        recorded["runtime_adapter"] = runtime_adapter
        return "pt-session"

    ui_app._load_prompt_toolkit_runner = lambda: fake_prompt_toolkit_runner
    try:
        session_key = run_ui(session_key="a1b2c3d4")
    finally:
        ui_app._load_prompt_toolkit_runner = original_loader

    assert session_key == "pt-session"
    assert recorded["session_key"] == "a1b2c3d4"
    assert recorded["runtime_adapter"] is not None


def test_run_ui_surfaces_prompt_toolkit_import_error() -> None:
    original_loader = ui_app._load_prompt_toolkit_runner

    def fake_loader():
        raise ImportError("prompt_toolkit is not installed")

    ui_app._load_prompt_toolkit_runner = fake_loader
    try:
        with pytest.raises(ImportError, match="prompt_toolkit is not installed"):
            run_ui(session_key="a1b2c3d4")
    finally:
        ui_app._load_prompt_toolkit_runner = original_loader


def test_main_runs_ui() -> None:
    called = {"run_ui": False}
    original_run_ui = ui_app.run_ui

    def fake_run_ui() -> str:
        called["run_ui"] = True
        return "session"

    ui_app.run_ui = fake_run_ui
    try:
        ui_app.main()
    finally:
        ui_app.run_ui = original_run_ui

    assert called["run_ui"] is True
