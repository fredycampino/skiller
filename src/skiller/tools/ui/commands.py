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
class RunsCommand:
    statuses: list[str]


@dataclass(frozen=True)
class WebhooksCommand:
    pass


@dataclass(frozen=True)
class ClearCommand:
    pass


@dataclass(frozen=True)
class RunCommand:
    raw_args: str


@dataclass(frozen=True)
class StatusCommand:
    run_id: str


@dataclass(frozen=True)
class LogsCommand:
    run_id: str


@dataclass(frozen=True)
class WatchCommand:
    run_id: str


@dataclass(frozen=True)
class ResumeCommand:
    run_id: str


@dataclass(frozen=True)
class InputCommand:
    run_id: str
    text: str


UiCommand = (
    EchoCommand
    | ExitCommand
    | HelpCommand
    | SessionCommand
    | RunsCommand
    | WebhooksCommand
    | ClearCommand
    | RunCommand
    | StatusCommand
    | LogsCommand
    | WatchCommand
    | ResumeCommand
    | InputCommand
    | None
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

    if normalized.startswith("/runs"):
        remainder = normalized[5:].strip()
        statuses: list[str] = []
        if remainder:
            parts = remainder.split()
            index = 0
            while index < len(parts):
                part = parts[index]
                if part == "--status" and index + 1 < len(parts):
                    statuses.append(parts[index + 1])
                    index += 2
                    continue
                index += 1
        return RunsCommand(statuses=statuses)

    if normalized == "/webhooks":
        return WebhooksCommand()

    if normalized in {"/clear", "/clean"}:
        return ClearCommand()

    if normalized in {"/exit", "/quit"}:
        return ExitCommand()

    if normalized.startswith("/run"):
        raw_args = normalized[4:].strip()
        return RunCommand(raw_args=raw_args)

    if normalized.startswith("/status"):
        run_id = normalized[7:].strip()
        return StatusCommand(run_id=run_id)

    if normalized.startswith("/logs"):
        run_id = normalized[5:].strip()
        return LogsCommand(run_id=run_id)

    if normalized.startswith("/watch"):
        run_id = normalized[6:].strip()
        return WatchCommand(run_id=run_id)

    if normalized.startswith("/resume"):
        run_id = normalized[7:].strip()
        return ResumeCommand(run_id=run_id)

    if normalized.startswith("/input"):
        remainder = normalized[6:].strip()
        if not remainder:
            return InputCommand(run_id="", text="")
        parts = remainder.split(maxsplit=1)
        if len(parts) == 1:
            return InputCommand(run_id=parts[0], text="")
        return InputCommand(run_id=parts[0], text=parts[1])

    if normalized.lower() in {"exit", "quit"}:
        return ExitCommand()

    return EchoCommand(message=message)
