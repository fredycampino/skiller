from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TuiStrings:
    intro_title: str = "Skiller stui"
    intro_body: str = "Run agents and inspect their execution transcript."
    intro_hint: str = "Use / to see the commands"


DEFAULT_TUI_STRINGS = TuiStrings()
