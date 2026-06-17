from __future__ import annotations

import pytest

import stui.usecase.select_model_use_case as select_model_use_case_module
from apps.tui.tests.support import FakeModelsPort, patched_to_thread
from stui.port.models_port import ModelsPortModelItem, ModelsPortProviderItem
from stui.usecase.run_event_context import RunEventContext, RunMode, RunStatus
from stui.usecase.select_model_use_case import SelectModelUseCase
from stui.viewmodel.console_screen_state import (
    ConsoleScreenState,
    DispatchErrorItem,
    PromptMode,
    ViewStatusKind,
)

pytestmark = pytest.mark.unit


def test_select_model_use_case_selects_and_refreshes_models() -> None:
    async def run() -> None:
        port = FakeModelsPort(models=_models())
        state = ConsoleScreenState()
        state.set_models_table(
            visible=True,
            command="/models",
            rows=_models(),
        )

        result = await SelectModelUseCase(
            models_port=port,
            context=_context(run_id="run-123"),
        ).execute(
            state=state,
            provider="minimax",
            model="MiniMax-M2.5",
        )

        assert result.selected is True
        assert port.select_called_with == [
            ("run-123", "minimax", "MiniMax-M2.5"),
        ]
        assert port.called_with == ["run-123"]
        assert result.state.models_table.visible is True
        assert result.state.models_table.command == "/models"
        assert result.state.prompt.mode == PromptMode.MODELS_TABLE
        assert result.state.view_status.kind == ViewStatusKind.HIDDEN
        providers = {provider.name: provider for provider in result.state.models_table.rows}
        minimax_models = {
            model.name: model for model in providers["minimax"].models
        }
        codex_models = {model.name: model for model in providers["codex"].models}
        assert minimax_models["MiniMax-M2.5"].active is True
        assert minimax_models["MiniMax-M2.7"].active is False
        assert codex_models["gpt-5.5"].active is False

    with patched_to_thread(select_model_use_case_module):
        import asyncio

        asyncio.run(run())


def test_select_model_use_case_reports_missing_active_run() -> None:
    async def run() -> None:
        port = FakeModelsPort(models=_models())
        state = ConsoleScreenState()
        state.set_models_table(visible=True, command="/models", rows=_models())

        result = await SelectModelUseCase(
            models_port=port,
            context=_context(run_id=""),
        ).execute(
            state=state,
            provider="minimax",
            model="MiniMax-M2.5",
        )

        assert result.selected is False
        assert port.select_called_with == []
        assert result.state.prompt.mode == PromptMode.MODELS_TABLE
        assert result.state.view_status.kind == ViewStatusKind.ERROR
        assert isinstance(result.state.transcript.items[0], DispatchErrorItem)
        assert "active run" in result.state.transcript.items[0].message

    with patched_to_thread(select_model_use_case_module):
        import asyncio

        asyncio.run(run())


def test_select_model_use_case_reports_runtime_errors() -> None:
    async def run() -> None:
        port = FakeModelsPort(
            models=_models(),
            select_error=RuntimeError("model selection failed"),
        )
        state = ConsoleScreenState()
        state.set_models_table(visible=True, command="/models", rows=_models())

        result = await SelectModelUseCase(
            models_port=port,
            context=_context(run_id="run-123"),
        ).execute(
            state=state,
            provider="minimax",
            model="MiniMax-M2.5",
        )

        assert result.selected is False
        assert port.select_called_with == [
            ("run-123", "minimax", "MiniMax-M2.5"),
        ]
        assert result.state.models_table.visible is True
        assert result.state.prompt.mode == PromptMode.MODELS_TABLE
        assert result.state.view_status.kind == ViewStatusKind.ERROR
        assert isinstance(result.state.transcript.items[0], DispatchErrorItem)
        assert "model selection failed" in result.state.transcript.items[0].message

    with patched_to_thread(select_model_use_case_module):
        import asyncio

        asyncio.run(run())


def _context(*, run_id: str) -> RunEventContext:
    return RunEventContext(
        run_id=run_id,
        run_name="chat",
        mode=RunMode.CHAT,
        status=RunStatus.RUNNING,
    )


def _models() -> list[ModelsPortProviderItem]:
    return [
        ModelsPortProviderItem(
            name="codex",
            source="global",
            models=(ModelsPortModelItem(name="gpt-5.5", active=True),),
        ),
        ModelsPortProviderItem(
            name="minimax",
            source="global",
            models=(
                ModelsPortModelItem(name="MiniMax-M2.7"),
                ModelsPortModelItem(name="MiniMax-M2.5"),
            ),
        ),
    ]
