from __future__ import annotations

import asyncio

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static

from stui.screen.agent_context_stats_view import AgentContextStatsView
from stui.screen.theme import build_textual_css
from stui.viewmodel.console_screen_state import AgentContextStatsState

pytestmark = pytest.mark.unit


def test_agent_context_stats_view_renders_empty_without_state() -> None:
    view = AgentContextStatsView()

    assert view.display is False


def test_agent_context_stats_view_renders_context_graphs() -> None:
    async def run() -> None:
        app = _AgentContextStatsHarness(state=_context_state())
        async with app.run_test() as pilot:
            await pilot.pause()
            content = app.query_one("#agent-context-stats-content", Static)
            view = app.query_one(AgentContextStatsView)

            rendered = str(content.content)
            assert view.display is True
            assert "Agent Context" in rendered
            assert "truncate 0/24" in rendered
            assert "2.6k" in rendered
            assert "limit 80K" in rendered
            assert "100K" in rendered
            assert "max 100K" not in rendered
            assert "┴" in rendered
            assert "▾" in rendered

    asyncio.run(run())


def _context_state() -> AgentContextStatsState:
    return AgentContextStatsState(
        entries=24,
        estimated_tokens=2618,
        start_sequence=1,
        end_sequence=24,
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
