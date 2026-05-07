from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class CommandKind(StrEnum):
    EMPTY = "empty"
    QUIT = "quit"
    RUN = "run"
    RUNS = "runs"
    AGENTS = "agents"
    FREE_TEXT = "free_text"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Command:
    kind: CommandKind
    name: str
    raw_text: str
    params: tuple[str, ...] = ()
    args_text: str = ""


@dataclass(frozen=True)
class NormalizeCommandUseCase:
    def execute(self, *, text: str) -> Command:
        normalized = text.strip()
        if not normalized:
            return Command(
                kind=CommandKind.EMPTY,
                name="",
                raw_text="",
            )

        lowered = normalized.lower()
        if lowered in {"/quit", "quit", "exit"}:
            return Command(
                kind=CommandKind.QUIT,
                name="quit",
                raw_text=normalized,
            )

        if not normalized.startswith("/"):
            return Command(
                kind=CommandKind.FREE_TEXT,
                name="text",
                raw_text=normalized,
            )

        command_name, params, args_text = _split_command(normalized)
        kind = _resolve_command_kind(command_name)
        return Command(
            kind=kind,
            name=command_name,
            raw_text=normalized,
            params=params,
            args_text=args_text,
        )


def _split_command(command_text: str) -> tuple[str, tuple[str, ...], str]:
    parts = command_text.split()
    if not parts:
        return "", (), ""

    command_name = parts[0].lower()
    params = tuple(parts[1:])
    if len(parts) == 1:
        return command_name, params, ""

    _, _, args_text = command_text.partition(" ")
    return command_name, params, args_text.strip()


def _resolve_command_kind(command_name: str) -> CommandKind:
    if command_name == "/run":
        return CommandKind.RUN
    if command_name == "/runs":
        return CommandKind.RUNS
    if command_name == "/agents":
        return CommandKind.AGENTS
    return CommandKind.UNKNOWN
