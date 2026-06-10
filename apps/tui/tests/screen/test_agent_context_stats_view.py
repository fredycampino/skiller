from __future__ import annotations

import asyncio

import pytest
from rich.text import Text
from textual.app import App, ComposeResult
from textual.widgets import Static

from stui.screen.agent_context_stats_view import AgentContextStatsView
from stui.screen.theme import build_textual_css
from stui.viewmodel.console_screen_state import AgentContextStatsState

pytestmark = pytest.mark.unit


def test_agent_context_stats_view_renders_empty_without_state() -> None:
    view = AgentContextStatsView()

    assert view.display is False


def test_agent_context_stats_view_renders_compact_muted_window_range() -> None:
    async def run() -> None:
        app = _AgentContextStatsHarness(state=_context_state())
        async with app.run_test(size=(34, 10)) as pilot:
            await pilot.pause()
            content = app.query_one("#agent-context-stats-content", Static)
            view = app.query_one(AgentContextStatsView)

            rendered = str(content.content)
            lines = rendered.splitlines()
            assert view.display is True
            assert len(lines) == 2
            assert "100" in lines[0]
            assert "1100" in lines[0]
            assert len(lines[1]) == 24
            assert lines[1].startswith("▪")
            assert lines[1].endswith("▪")
            assert "▾" in lines[1]
            assert "─" in lines[1]
            assert "━" in lines[1]
            assert isinstance(content.content, Text)
            assert str(content.content.style) == "#555555"
            assert "Agent Context" not in rendered
            assert "truncate" not in rendered
            assert "limit" not in rendered

    asyncio.run(run())


def _context_state() -> AgentContextStatsState:
    return AgentContextStatsState(
        entries=1001,
        estimated_tokens=2618,
        start_sequence=100,
        end_sequence=1100,
        current_tokens=2618,
        limit_tokens=80000,
        capacity_tokens=100000,
    )


class _AgentContextStatsHarness(App[None]):
    CSS = build_textual_css()

    def __init__(self, *, state: AgentContextStatsState | None) -> None:
        super().__init__()
        self.context_state = state

    def compose(self) -> ComposeResult:
        yield AgentContextStatsView(state=self.context_state)
