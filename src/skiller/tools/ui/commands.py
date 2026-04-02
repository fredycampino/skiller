from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


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
class ServerStatusCommand:
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
class BodyCommand:
    body_ref: str


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


@dataclass(frozen=True)
class CommandSpec:
    name: str
    usage: str
    description: str
    aliases: tuple[str, ...] = ()


UiCommand = (
    EchoCommand
    | ExitCommand
    | HelpCommand
    | SessionCommand
    | ServerStatusCommand
    | RunsCommand
    | WebhooksCommand
    | ClearCommand
    | RunCommand
    | StatusCommand
    | LogsCommand
    | BodyCommand
    | WatchCommand
    | ResumeCommand
    | InputCommand
    | None
)


COMMAND_SPECS = (
    CommandSpec(name="/help", usage="/help", description="Show this help"),
    CommandSpec(
        name="/session",
        usage="/session",
        description="Show known runs and current selection",
    ),
    CommandSpec(
        name="/server",
        usage="/server status",
        description="Show local webhooks server status",
    ),
    CommandSpec(
        name="/runs",
        usage="/runs",
        description="Show recent persisted runs",
    ),
    CommandSpec(
        name="/webhooks",
        usage="/webhooks",
        description="Show registered webhook channels",
    ),
    CommandSpec(
        name="/clear",
        usage="/clear",
        description="Clear the screen",
        aliases=("/clean",),
    ),
    CommandSpec(
        name="/run",
        usage="/run <args>",
        description="Run a skill, for example: /run notify_test",
    ),
    CommandSpec(
        name="/run-file",
        usage="/run --file <path>",
        description="Run a skill file, for example: /run --file skill.yaml",
    ),
    CommandSpec(
        name="/status",
        usage="/status <run_id>",
        description="Show run status",
    ),
    CommandSpec(
        name="/logs",
        usage="/logs [run_id]",
        description="Show recent run logs for the selected or last run",
    ),
    CommandSpec(
        name="/body",
        usage="/body <body_ref>",
        description="Show persisted output body for a body_ref",
    ),
    CommandSpec(
        name="/watch",
        usage="/watch <run_id>",
        description="Watch a run until it stops",
    ),
    CommandSpec(
        name="/input",
        usage="/input <run_id> <text>",
        description="Send text to a waiting input step",
    ),
    CommandSpec(
        name="/resume",
        usage="/resume <run_id>",
        description="Resume a waiting run",
    ),
    CommandSpec(
        name="/exit",
        usage="/exit",
        description="Exit the UI",
        aliases=("/quit",),
    ),
)


_COMMAND_SPECS_BY_NAME = {
    alias: spec
    for spec in COMMAND_SPECS
    for alias in (spec.name, *spec.aliases)
}


def get_canonical_command_names() -> list[str]:
    return [spec.name for spec in COMMAND_SPECS if spec.name != "/run-file"]


def iter_help_lines() -> Iterable[str]:
    for spec in COMMAND_SPECS:
        yield f"  {spec.usage:<26} {spec.description}"


def parse_command(raw_line: str) -> UiCommand:
    message = raw_line.rstrip("\n")
    normalized = message.strip()

    if not normalized:
        return None

    if normalized.lower() in {"exit", "quit"}:
        return ExitCommand()

    if not normalized.startswith("/"):
        return EchoCommand(message=message)

    command_name, _, remainder = normalized.partition(" ")
    resolved_name = _resolve_command_name(command_name)

    if resolved_name == "/help":
        return HelpCommand()

    if resolved_name == "/session":
        return SessionCommand()

    if resolved_name == "/server":
        return ServerStatusCommand()

    if resolved_name == "/runs":
        remainder = remainder.strip()
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
                statuses.append(part)
                index += 1
        return RunsCommand(statuses=statuses)

    if resolved_name == "/webhooks":
        return WebhooksCommand()

    if resolved_name == "/clear":
        return ClearCommand()

    if resolved_name == "/exit":
        return ExitCommand()

    if resolved_name == "/run" or command_name == "/run":
        raw_args = remainder.strip()
        return RunCommand(raw_args=raw_args)

    if resolved_name == "/status":
        run_id = remainder.strip()
        return StatusCommand(run_id=run_id)

    if resolved_name == "/logs":
        run_id = remainder.strip()
        return LogsCommand(run_id=run_id)

    if resolved_name == "/body":
        body_ref = remainder.strip()
        return BodyCommand(body_ref=body_ref)

    if resolved_name == "/watch":
        run_id = remainder.strip()
        return WatchCommand(run_id=run_id)

    if resolved_name == "/resume":
        run_id = remainder.strip()
        return ResumeCommand(run_id=run_id)

    if resolved_name == "/input":
        input_remainder = remainder.strip()
        if not input_remainder:
            return InputCommand(run_id="", text="")
        parts = input_remainder.split(maxsplit=1)
        if len(parts) == 1:
            return InputCommand(run_id=parts[0], text="")
        return InputCommand(run_id=parts[0], text=parts[1])

    return EchoCommand(message=message)


def _resolve_command_name(command_name: str) -> str | None:
    spec = _COMMAND_SPECS_BY_NAME.get(command_name)
    if spec is not None:
        return spec.name
    return None
