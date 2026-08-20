from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from typing import TypeVar

import pytest

import stui.usecase.auth_command_use_case as auth_command_use_case_module
from apps.tui.tests.support import FakeModelsPort, patched_to_thread
from stui.di.strings import TuiStrings
from stui.port.models_port import AuthProvidersPortModelItem, AuthProvidersPortProviderItem
from stui.usecase.auth_command_use_case import AuthCommandUseCase
from stui.usecase.normalize_command_use_case import NormalizeCommandUseCase
from stui.usecase.run_event_context import RunEventContext, RunMode, RunStatus

pytestmark = pytest.mark.unit

_T = TypeVar("_T")

_ADAPTER_BY_PROVIDER = {
    "codex": "codex",
    "minimax": "openai",
    "bedrock": "bedrock",
    "moonshot": "openai",
    "lmstudio": "openai",
    "openrouter": "openai",
}


def _run(coro: Awaitable[_T]) -> _T:
    with patched_to_thread(auth_command_use_case_module):
        return asyncio.run(coro)


def _port() -> FakeModelsPort:
    return FakeModelsPort(
        providers=[
            AuthProvidersPortProviderItem(
                name=name,
                source="user",
                adapter=adapter,
                models=(
                    AuthProvidersPortModelItem(name=f"{name}-m1"),
                ),
            )
            for name, adapter in _ADAPTER_BY_PROVIDER.items()
        ]
    )


@pytest.mark.parametrize(
    ("text", "run_args"),
    [
        ("/auth codex", "auths/codex"),
        ("/auth minimax", "auths/openai --arg provider=minimax"),
        ("/auth bedrock", "auths/bedrock"),
        ("/auth moonshot", "auths/openai --arg provider=moonshot"),
        ("/auth lmstudio", "auths/lmstudio"),
        ("/auth openrouter", "auths/openai --arg provider=openrouter"),
        ("/auth CODEX", "auths/codex"),
    ],
)
def test_auth_command_use_case_maps_provider(text: str, run_args: str) -> None:
    result = _run(
        AuthCommandUseCase(context=_context(), models_port=_port()).execute(
            command=NormalizeCommandUseCase().execute(text=text)
        )
    )

    assert result.command is not None
    assert result.command.args_text == run_args


def test_auth_command_use_case_rejects_unknown_provider() -> None:
    result = _run(
        AuthCommandUseCase(context=_context(), models_port=_port()).execute(
            command=NormalizeCommandUseCase().execute(text="/auth unknown")
        )
    )

    assert result.command is None
    assert result.error_message == (
        "Unknown auth provider. Use /auth to list available providers, "
        "or /auth <provider> to configure one."
    )


def test_auth_command_use_case_reports_providers_query_failure() -> None:
    port = FakeModelsPort(error=RuntimeError("providers command failed"))

    result = _run(
        AuthCommandUseCase(context=_context(), models_port=port).execute(
            command=NormalizeCommandUseCase().execute(text="/auth minimax")
        )
    )

    assert result.command is None
    assert result.error_message == "Failed to load auth providers: providers command failed"


def test_auth_command_use_case_rejects_provider_without_flow() -> None:
    port = FakeModelsPort(
        providers=[
            AuthProvidersPortProviderItem(
                name="custom",
                source="none",
                adapter="mystery",
                models=(),
            )
        ]
    )
    result = _run(
        AuthCommandUseCase(context=_context(), models_port=port).execute(
            command=NormalizeCommandUseCase().execute(text="/auth custom")
        )
    )

    assert result.command is None
    assert result.error_message == (
        "Unknown auth provider. Use /auth to list available providers, "
        "or /auth <provider> to configure one."
    )


def test_auth_command_use_case_uses_string_for_unknown_provider() -> None:
    result = _run(
        AuthCommandUseCase(
            context=_context(),
            models_port=_port(),
            strings=TuiStrings(auth_unknown_provider_message="Choose a known provider."),
        ).execute(command=NormalizeCommandUseCase().execute(text="/auth unknown"))
    )

    assert result.command is None
    assert result.error_message == "Choose a known provider."


def test_auth_command_use_case_rejects_extra_args() -> None:
    result = _run(
        AuthCommandUseCase(context=_context(), models_port=_port()).execute(
            command=NormalizeCommandUseCase().execute(text="/auth codex extra")
        )
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
    result = _run(
        AuthCommandUseCase(
            context=_context(run_id="waiting-run", status=status),
            models_port=_port(),
        ).execute(command=NormalizeCommandUseCase().execute(text="/auth codex"))
    )

    assert result.command is not None
    assert result.command.args_text == "auths/codex --arg continue_id=waiting-run"


def test_auth_command_use_case_does_not_pass_continue_id_when_running() -> None:
    result = _run(
        AuthCommandUseCase(
            context=_context(run_id="running-run", status=RunStatus.RUNNING),
            models_port=_port(),
        ).execute(command=NormalizeCommandUseCase().execute(text="/auth codex"))
    )

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
