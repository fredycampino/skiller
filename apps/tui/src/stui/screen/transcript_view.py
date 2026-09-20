from __future__ import annotations

from typing import Protocol

from rich.console import RenderableType
from textual import events
from textual.selection import Selection
from textual.widgets import RichLog

from stui.screen.theme import TuiTheme
from stui.viewmodel.console_screen_state import TranscriptItem, TranscriptMode, TranscriptState


class TranscriptRenderer(Protocol):
    def render(
        self,
        *,
        items: list[TranscriptItem],
        mode: TranscriptMode,
        theme: TuiTheme,
        prompt_placeholder: str | None,
    ) -> list[RenderableType]: ...


class TranscriptView(RichLog):
    def __init__(
        self,
        *args,  # noqa: ANN002
        renderer: TranscriptRenderer,
        theme: TuiTheme,
        **kwargs,  # noqa: ANN003
    ) -> None:
        super().__init__(*args, **kwargs)
        self._renderer = renderer
        self._theme = theme
        self._state: TranscriptState | None = None
        self._rendered_snapshot: tuple[
            int,
            TranscriptMode,
            tuple[TranscriptItem, ...],
        ] | None = None

    def set_state(self, state: TranscriptState) -> None:
        self._state = TranscriptState(mode=state.mode, items=list(state.items))
        snapshot = (
            self.size.width,
            state.mode,
            tuple(state.items),
        )
        if snapshot == self._rendered_snapshot:
            return

        renderables = self._renderer.render(
            items=state.items,
            mode=state.mode,
            theme=self._theme,
            prompt_placeholder="",
        )
        with self.app.batch_update():
            self.clear()
            for index, renderable in enumerate(renderables):
                self.write(
                    renderable,
                    expand=True,
                    scroll_end=index == len(renderables) - 1,
                )
        self._rendered_snapshot = snapshot

    def on_resize(self, _: events.Resize) -> None:
        if self.size.width <= 0 or self._state is None:
            return
        self.set_state(self._state)

    def get_selection(self, selection: Selection) -> tuple[str, str] | None:
        if not self.lines:
            return None

        text = "\n".join(strip.text for strip in self.lines)
        return selection.extract(text), "\n"
