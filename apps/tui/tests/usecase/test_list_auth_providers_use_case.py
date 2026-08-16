from __future__ import annotations

import asyncio

import pytest

import stui.usecase.list_auth_providers_use_case as list_auth_providers_use_case_module
from apps.tui.tests.support import FakeModelsPort, patched_to_thread
from stui.port.models_port import ModelsPortProviderItem
from stui.usecase.list_auth_providers_use_case import ListAuthProvidersUseCase
from stui.usecase.normalize_command_use_case import Command, CommandKind
from stui.usecase.run_event_context import RunEventContext, RunMode, RunStatus
from stui.viewmodel.console_screen_state import (
    ConsoleScreenState,
    DispatchErrorItem,
    PromptMode,
    ViewStatusKind,
)

pytestmark = pytest.mark.unit


def test_list_auth_providers_use_case_opens_ordered_auth_table() -> None:
    async def run() -> None:
        state = ConsoleScreenState()
        port = FakeModelsPort(
            models=[ModelsPortProviderItem(name="codex", source="user", models=())]
        )

        result = await ListAuthProvidersUseCase(
            models_port=port,
            context=_context(run_id="run-123"),
        ).execute(state=state, command=_auth_command())

        assert port.called_with == ["run-123"]
        assert result.state.auth_table.visible is True
        assert [row.name for row in result.state.auth_table.rows] == [
            "moonshot",
            "codex",
            "bedrock",
            "minimax",
            "lmstudio",
        ]
        assert result.state.auth_table.rows[1].source == "user"
        assert result.state.auth_table.rows[0].source == "none"
        assert result.state.prompt.mode == PromptMode.AUTH_TABLE

    with patched_to_thread(list_auth_providers_use_case_module):
        asyncio.run(run())


def test_list_auth_providers_use_case_reports_missing_active_run() -> None:
    async def run() -> None:
        state = ConsoleScreenState()
        port = FakeModelsPort()

        result = await ListAuthProvidersUseCase(
            models_port=port,
            context=_context(run_id=""),
        ).execute(state=state, command=_auth_command())

        assert port.called is False
        assert result.state.auth_table.visible is False
        assert result.state.prompt.mode == PromptMode.DEFAULT
        assert result.state.view_status.kind == ViewStatusKind.ERROR
        assert isinstance(result.state.transcript.items[0], DispatchErrorItem)

    asyncio.run(run())


def _context(*, run_id: str) -> RunEventContext:
    return RunEventContext(
        run_id=run_id,
        run_name="chat",
        mode=RunMode.CHAT,
        status=RunStatus.RUNNING,
    )


def _auth_command() -> Command:
    return Command(kind=CommandKind.AUTH, name="/auth", raw_text="/auth")
