from __future__ import annotations

from typing import TextIO

from skiller.tools.ui.session import UiRun, UiSession


def write_welcome(*, stdout: TextIO, session: UiSession) -> None:
    stdout.write(f"session_key: {session.session_key}\n")
    stdout.write("Type a message and press Enter. Type 'exit' to quit.\n")
    stdout.flush()


def write_prompt(*, stdout: TextIO) -> None:
    stdout.write("> ")
    stdout.flush()


def write_echo(*, stdout: TextIO, session: UiSession, message: str) -> None:
    stdout.write(f"[{session.session_key}] echo: {message}\n")
    stdout.flush()


def write_help(*, stdout: TextIO) -> None:
    stdout.write("Commands: /help, /session, /clear, /run <args>, /exit\n")
    stdout.write(
        "Tip: /run forwards args to `skiller run`, including flags "
        "like --file and --start-webhooks\n"
    )
    stdout.flush()


def write_session(*, stdout: TextIO, session: UiSession) -> None:
    stdout.write(f"session_key: {session.session_key}\n")
    stdout.flush()


def write_clear(*, stdout: TextIO) -> None:
    stdout.write("\033[2J\033[H")
    stdout.flush()


def write_run_result(*, stdout: TextIO, session: UiSession, run: UiRun) -> None:
    _ = session
    args_label = run.raw_args or "<empty>"
    stdout.write(f"run_id: {run.run_id} status: {run.status} args: {args_label}\n")
    if run.error:
        stdout.write(f"error: {run.error}\n")
    stdout.flush()


def write_runs_table(*, stdout: TextIO, session: UiSession) -> None:
    if not session.runs:
        stdout.write("runs: []\n")
        stdout.flush()
        return

    for index, run in enumerate(session.runs, start=1):
        args_label = run.raw_args or "<empty>"
        error_label = f" error={run.error}" if run.error else ""
        stdout.write(f"runs[{index}]: {run.run_id} {run.status} {args_label}{error_label}\n")
    stdout.flush()


def write_bye(*, stdout: TextIO) -> None:
    stdout.write("bye\n")
    stdout.flush()
