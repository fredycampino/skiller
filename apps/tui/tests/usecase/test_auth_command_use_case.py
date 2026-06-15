from __future__ import annotations

import pytest

from stui.di.strings import TuiStrings
from stui.usecase.auth_command_use_case import AuthCommandUseCase
from stui.usecase.normalize_command_use_case import CommandKind, NormalizeCommandUseCase
from stui.usecase.run_event_context import RunEventContext, RunMode, RunStatus

pytestmark = pytest.mark.unit


def test_auth_command_use_case_maps_auth_menu() -> None:
    result = AuthCommandUseCase(context=_context()).execute(
        command=NormalizeCommandUseCase().execute(text="/auth")
    )

    assert result.command is not None
    assert result.command.kind == CommandKind.RUN
    assert result.command.args_text == "auths/auth"
    assert result.command.raw_text == "/auth"


@pytest.mark.parametrize(
    ("text", "run_args"),
    [
        ("/auth codex", "auths/codex"),
        ("/auth minimax", "auths/minimax"),
        ("/auth bedrock", "auths/bedrock"),
        ("/auth CODEX", "auths/codex"),
    ],
)
def test_auth_command_use_case_maps_provider(text: str, run_args: str) -> None:
    result = AuthCommandUseCase(context=_context()).execute(
        command=NormalizeCommandUseCase().execute(text=text)
    )

    assert result.command is not None
    assert result.command.args_text == run_args


def test_auth_command_use_case_rejects_unknown_provider() -> None:
    result = AuthCommandUseCase(context=_context()).execute(
        command=NormalizeCommandUseCase().execute(text="/auth unknown")
    )

    assert result.command is None
    assert result.error_message == (
        "Unknown auth provider. Use /auth, /auth codex, /auth minimax, or /auth bedrock."
    )


def test_auth_command_use_case_uses_string_for_unknown_provider() -> None:
    result = AuthCommandUseCase(
        context=_context(),
        strings=TuiStrings(auth_unknown_provider_message="Choose a known provider.")
    ).execute(command=NormalizeCommandUseCase().execute(text="/auth unknown"))

    assert result.command is None
    assert result.error_message == "Choose a known provider."


def test_auth_command_use_case_rejects_extra_args() -> None:
    result = AuthCommandUseCase(context=_context()).execute(
        command=NormalizeCommandUseCase().execute(text="/auth codex extra")
    )

    assert result.command is None


@pytest.mark.parametrize(
    "status",
    [
        RunStatus.WAITING_INPUT,
        RunStatus.WAITING_WEBHOOK,
        RunStatus.WAITING_CHANNEL,
    ],
)
def test_auth_command_use_case_passes_continue_id_when_waiting(
    status: RunStatus,
) -> None:
    result = AuthCommandUseCase(
        context=_context(run_id="waiting-run", status=status)
    ).execute(command=NormalizeCommandUseCase().execute(text="/auth codex"))

    assert result.command is not None
    assert result.command.args_text == "auths/codex --arg continue_id=waiting-run"


def test_auth_command_use_case_does_not_pass_continue_id_when_running() -> None:
    result = AuthCommandUseCase(
        context=_context(run_id="running-run", status=RunStatus.RUNNING)
    ).execute(command=NormalizeCommandUseCase().execute(text="/auth codex"))

    assert result.command is not None
    assert result.command.args_text == "auths/codex"


def _context(
    *,
    run_id: str = "",
    status: RunStatus = RunStatus.RUNNING,
) -> RunEventContext:
    return RunEventContext(
        run_id=run_id,
        run_name="",
        mode=RunMode.CHAT,
        status=status,
    )
