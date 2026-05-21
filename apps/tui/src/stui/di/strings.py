from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TuiStrings:
    intro_title: str = "Skiller.run stui"
    intro_body: str = "Run agents, flows and tools."
    intro_hint: str = "Use / to see the commands"
    unsupported_input_message: str = "Use /run <agent> to execute an agent."


DEFAULT_TUI_STRINGS = TuiStrings()
