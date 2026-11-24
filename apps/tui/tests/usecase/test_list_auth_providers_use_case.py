from __future__ import annotations

import asyncio

import pytest

import stui.usecase.list_auth_providers_use_case as list_auth_providers_use_case_module
from apps.tui.tests.support import FakeModelsPort, patched_to_thread
from stui.port.models_port import AuthProvidersPortProviderItem
from stui.usecase.list_auth_providers_use_case import ListAuthProvidersUseCase
from stui.usecase.normalize_command_use_case import Command, CommandKind
from stui.viewmodel.console_screen_state import (
    ConsoleScreenState,
    DispatchErrorItem,
    PromptMode,
    ViewStatusKind,
)

pytestmark = pytest.mark.unit


def test_list_auth_providers_use_case_opens_auth_table_with_port_providers() -> None:
    async def run() -> None:
        state = ConsoleScreenState()
        port = FakeModelsPort(
            providers=[
                AuthProvidersPortProviderItem(
                    name="moonshot", source="user", adapter="openai", models=()
                ),
                AuthProvidersPortProviderItem(
                    name="codex", source="user", adapter="codex", models=()
                ),
                AuthProvidersPortProviderItem(
                    name="openrouter", source="default", adapter="openai", models=()
                ),
            ]
        )

        result = await ListAuthProvidersUseCase(models_port=port).execute(
            state=state,
            command=_auth_command(),
        )

        assert port.providers_called is True
        assert port.called is False
        assert result.state.auth_table.visible is True
        assert [row.name for row in result.state.auth_table.rows] == [
            "codex",
            "openrouter",
            "moonshot",
        ]
        assert [row.adapter for row in result.state.auth_table.rows] == [
            "codex",
            "openai",
            "openai",
        ]
        assert result.state.auth_table.rows[0].source == "user"
        assert result.state.auth_table.rows[1].source == "default"
        assert result.state.auth_table.rows[2].source == "user"
        assert result.state.prompt.mode == PromptMode.AUTH_TABLE

    with patched_to_thread(list_auth_providers_use_case_module):
        asyncio.run(run())


def test_list_auth_providers_use_case_reports_providers_query_failure() -> None:
    async def run() -> None:
        state = ConsoleScreenState()
        port = FakeModelsPort(error=RuntimeError("providers command failed"))

        result = await ListAuthProvidersUseCase(models_port=port).execute(
            state=state,
            command=_auth_command(),
        )

        assert port.providers_called is True
        assert result.state.auth_table.visible is False
        assert result.state.prompt.mode == PromptMode.DEFAULT
        assert result.state.view_status.kind == ViewStatusKind.ERROR
        assert isinstance(result.state.transcript.items[0], DispatchErrorItem)
        assert result.state.transcript.items[0].message == "error: providers command failed"

    with patched_to_thread(list_auth_providers_use_case_module):
        asyncio.run(run())


def _auth_command() -> Command:
    return Command(kind=CommandKind.AUTH, name="/auth", raw_text="/auth")


def test_auth_provider_priority_keeps_other_providers_after_known_ones() -> None:
    names = [
        "custom",
        "moonshot",
        "deepseek",
        "openrouter",
        "lmstudio",
        "ollama",
        "bedrock",
        "codex",
        "minimax",
    ]
    providers = [
        AuthProvidersPortProviderItem(name=name, source="default", adapter="openai", models=())
        for name in names
    ]
    with patched_to_thread(list_auth_providers_use_case_module):
        result = asyncio.run(
            ListAuthProvidersUseCase(models_port=FakeModelsPort(providers=providers)).execute(
                state=ConsoleScreenState(), command=_auth_command()
            )
        )
    assert [row.name for row in result.state.auth_table.rows] == [
        "codex",
        "bedrock",
        "ollama",
        "lmstudio",
        "openrouter",
        "deepseek",
        "moonshot",
        "minimax",
        "custom",
    ]
