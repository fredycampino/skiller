from __future__ import annotations

import sys
from typing import TextIO

from skiller.tools.ui.commands import (
    ClearCommand,
    EchoCommand,
    ExitCommand,
    HelpCommand,
    RunCommand,
    SessionCommand,
    parse_command,
)
from skiller.tools.ui.renderer import (
    write_bye,
    write_clear,
    write_echo,
    write_help,
    write_prompt,
    write_run_result,
    write_runs_table,
    write_session,
    write_welcome,
)
from skiller.tools.ui.runtime_adapter import execute_run
from skiller.tools.ui.session import UiRun, build_run_id, build_session


def run_ui(
    *,
    stdin: TextIO,
    stdout: TextIO,
    session_key: str | None = None,
) -> str:
    session = build_session(session_key)
    write_welcome(stdout=stdout, session=session)

    while True:
        write_prompt(stdout=stdout)

        raw_line = stdin.readline()
        if raw_line == "":
            break

        command = parse_command(raw_line)
        if command is None:
            continue

        if isinstance(command, ExitCommand):
            write_bye(stdout=stdout)
            break

        if isinstance(command, HelpCommand):
            write_help(stdout=stdout)
            continue

        if isinstance(command, SessionCommand):
            write_session(stdout=stdout, session=session)
            write_runs_table(stdout=stdout, session=session)
            continue

        if isinstance(command, ClearCommand):
            write_clear(stdout=stdout)
            continue

        if isinstance(command, RunCommand):
            run = UiRun(run_id=build_run_id(), raw_args=command.raw_args)
            session.runs.append(run)
            try:
                payload = execute_run(raw_args=command.raw_args)
                run.status = str(payload.get("status", "UNKNOWN"))
            except RuntimeError as exc:
                run.status = "FAILED"
                run.error = str(exc)
            write_run_result(stdout=stdout, session=session, run=run)
            continue

        if isinstance(command, EchoCommand):
            write_echo(stdout=stdout, session=session, message=command.message)

    return session.session_key


def main() -> None:
    run_ui(stdin=sys.stdin, stdout=sys.stdout)
