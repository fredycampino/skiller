from __future__ import annotations

import pytest

from stui.di.strings import TuiStrings
from stui.usecase.auth_command_use_case import AuthCommandUseCase
from stui.usecase.normalize_command_use_case import CommandKind, NormalizeCommandUseCase

pytestmark = pytest.mark.unit


def test_auth_command_use_case_maps_auth_menu() -> None:
    result = AuthCommandUseCase().execute(
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
    result = AuthCommandUseCase().execute(
        command=NormalizeCommandUseCase().execute(text=text)
    )

    assert result.command is not None
    assert result.command.args_text == run_args


def test_auth_command_use_case_rejects_unknown_provider() -> None:
    result = AuthCommandUseCase().execute(
        command=NormalizeCommandUseCase().execute(text="/auth unknown")
    )

    assert result.command is None
    assert result.error_message == (
        "Unknown auth provider. Use /auth, /auth codex, /auth minimax, or /auth bedrock."
    )


def test_auth_command_use_case_uses_string_for_unknown_provider() -> None:
    result = AuthCommandUseCase(
        strings=TuiStrings(auth_unknown_provider_message="Choose a known provider.")
    ).execute(command=NormalizeCommandUseCase().execute(text="/auth unknown"))

    assert result.command is None
    assert result.error_message == "Choose a known provider."


def test_auth_command_use_case_rejects_extra_args() -> None:
    result = AuthCommandUseCase().execute(
        command=NormalizeCommandUseCase().execute(text="/auth codex extra")
    )

    assert result.command is None
