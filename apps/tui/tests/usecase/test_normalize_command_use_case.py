from __future__ import annotations

import pytest

from stui.usecase.normalize_command_use_case import (
    CommandKind,
    NormalizeCommandUseCase,
)

pytestmark = pytest.mark.unit


def test_normalize_command_use_case_returns_empty_for_blank_input() -> None:
    command = NormalizeCommandUseCase().execute(text="   ")

    assert command.kind == CommandKind.EMPTY
    assert command.raw_text == ""
    assert command.params == ()


def test_normalize_command_use_case_normalizes_run_command() -> None:
    command = NormalizeCommandUseCase().execute(text="  /run   chat  --mode fast  ")

    assert command.kind == CommandKind.RUN
    assert command.name == "/run"
    assert command.raw_text == "/run   chat  --mode fast"
    assert command.params == ("chat", "--mode", "fast")
    assert command.args_text == "chat  --mode fast"


def test_normalize_command_use_case_normalizes_runs_command() -> None:
    command = NormalizeCommandUseCase().execute(text="/runs waiting")

    assert command.kind == CommandKind.RUNS
    assert command.name == "/runs"
    assert command.params == ("waiting",)


def test_normalize_command_use_case_classifies_legacy_chat_commands_as_unknown() -> None:
    use_case = NormalizeCommandUseCase()

    assert use_case.execute(text="/chat ant").kind == CommandKind.UNKNOWN
    assert use_case.execute(text="/chats").kind == CommandKind.UNKNOWN


def test_normalize_command_use_case_normalizes_quit_variants() -> None:
    use_case = NormalizeCommandUseCase()

    assert use_case.execute(text="/quit").kind == CommandKind.QUIT
    assert use_case.execute(text="/exit").kind == CommandKind.QUIT
    assert use_case.execute(text="quit").kind == CommandKind.FREE_TEXT
    assert use_case.execute(text="exit").kind == CommandKind.FREE_TEXT


def test_normalize_command_use_case_classifies_free_text() -> None:
    command = NormalizeCommandUseCase().execute(text="hola mundo")

    assert command.kind == CommandKind.FREE_TEXT
    assert command.raw_text == "hola mundo"


def test_normalize_command_use_case_classifies_unknown_slash_commands() -> None:
    command = NormalizeCommandUseCase().execute(text="/resume run-1")

    assert command.kind == CommandKind.UNKNOWN
    assert command.name == "/resume"
    assert command.params == ("run-1",)
