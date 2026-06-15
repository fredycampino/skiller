from __future__ import annotations

import pytest

import stui.usecase.list_models_use_case as list_models_use_case_module
from apps.tui.tests.support import FakeModelsPort, patched_to_thread
from stui.port.models_port import ModelsPortModelItem, ModelsPortProviderItem
from stui.usecase.list_models_use_case import ListModelsUseCase
from stui.usecase.normalize_command_use_case import Command, CommandKind
from stui.usecase.run_event_context import RunEventContext, RunMode, RunStatus
from stui.viewmodel.console_screen_state import (
    ConsoleScreenState,
    DispatchErrorItem,
    PromptMode,
    ViewStatusKind,
)

pytestmark = pytest.mark.unit


def test_list_models_use_case_opens_models_table() -> None:
    async def run() -> None:
        models = [
            ModelsPortProviderItem(
                name="codex",
                source="global",
                models=(ModelsPortModelItem(name="gpt-5.5", active=True),),
            )
        ]
        port = FakeModelsPort(models=models)
        state = ConsoleScreenState()

        result = await ListModelsUseCase(
            models_port=port,
            context=_context(run_id="run-123"),
        ).execute(
            state=state,
            command=_models_command(),
        )

        assert port.called is True
        assert port.called_with == ["run-123"]
        assert result.state.models_table.visible is True
        assert result.state.models_table.command == "/models"
        assert result.state.models_table.rows == tuple(models)
        assert result.state.prompt.mode == PromptMode.MODELS_TABLE
        assert result.state.transcript.items == []

    with patched_to_thread(list_models_use_case_module):
        import asyncio

        asyncio.run(run())


def test_list_models_use_case_reports_errors() -> None:
    async def run() -> None:
        state = ConsoleScreenState()

        result = await ListModelsUseCase(
            models_port=FakeModelsPort(error=RuntimeError("boom")),
            context=_context(run_id="run-123"),
        ).execute(
            state=state,
            command=_models_command(),
        )

        assert result.state.models_table.visible is False
        assert result.state.prompt.mode == PromptMode.DEFAULT
        assert result.state.view_status.kind == ViewStatusKind.ERROR
        assert isinstance(result.state.transcript.items[0], DispatchErrorItem)

    with patched_to_thread(list_models_use_case_module):
        import asyncio

        asyncio.run(run())


def test_list_models_use_case_reports_missing_active_run() -> None:
    async def run() -> None:
        port = FakeModelsPort()
        state = ConsoleScreenState()

        result = await ListModelsUseCase(
            models_port=port,
            context=_context(run_id=""),
        ).execute(
            state=state,
            command=_models_command(),
        )

        assert port.called is False
        assert result.state.models_table.visible is False
        assert result.state.prompt.mode == PromptMode.DEFAULT
        assert result.state.view_status.kind == ViewStatusKind.ERROR
        assert isinstance(result.state.transcript.items[0], DispatchErrorItem)
        assert "active run" in result.state.transcript.items[0].message

    with patched_to_thread(list_models_use_case_module):
        import asyncio

        asyncio.run(run())


def _context(*, run_id: str) -> RunEventContext:
    return RunEventContext(
        run_id=run_id,
        run_name="chat",
        mode=RunMode.CHAT,
        status=RunStatus.RUNNING,
    )


def _models_command() -> Command:
    return Command(kind=CommandKind.MODELS, name="/models", raw_text="/models")
