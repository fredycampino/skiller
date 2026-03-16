from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EchoCommand:
    message: str


@dataclass(frozen=True)
class ExitCommand:
    pass


@dataclass(frozen=True)
class HelpCommand:
    pass


@dataclass(frozen=True)
class SessionCommand:
    pass


@dataclass(frozen=True)
class ClearCommand:
    pass


@dataclass(frozen=True)
class RunCommand:
    raw_args: str


UiCommand = (
    EchoCommand | ExitCommand | HelpCommand | SessionCommand | ClearCommand | RunCommand | None
)


def parse_command(raw_line: str) -> UiCommand:
    message = raw_line.rstrip("\n")
    normalized = message.strip()

    if not normalized:
        return None

    if normalized == "/help":
        return HelpCommand()

    if normalized == "/session":
        return SessionCommand()

    if normalized in {"/clear", "/clean"}:
        return ClearCommand()

    if normalized in {"/exit", "/quit"}:
        return ExitCommand()

    if normalized.startswith("/run"):
        raw_args = normalized[4:].strip()
        return RunCommand(raw_args=raw_args)

    if normalized.lower() in {"exit", "quit"}:
        return ExitCommand()

    return EchoCommand(message=message)
