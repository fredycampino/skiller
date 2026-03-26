from __future__ import annotations

import sys
from typing import TextIO

from skiller.tools.ui.actions import handle_command
from skiller.tools.ui.commands import parse_command
from skiller.tools.ui.renderer import (
    render_action_result,
    write_prompt,
    write_welcome,
)
from skiller.tools.ui.runtime_adapter import CliRuntimeAdapter
from skiller.tools.ui.session import build_session


def run_ui(
    *,
    stdin: TextIO,
    stdout: TextIO,
    session_key: str | None = None,
    runtime_adapter: CliRuntimeAdapter | None = None,
) -> str:
    session = build_session(session_key)
    runtime = runtime_adapter or CliRuntimeAdapter()
    write_welcome(stdout=stdout, session=session)

    while True:
        write_prompt(stdout=stdout)

        raw_line = stdin.readline()
        if raw_line == "":
            break

        command = parse_command(raw_line)
        result = handle_command(session=session, command=command, runtime=runtime)
        render_action_result(stdout=stdout, session=session, result=result)
        if result.kind == "exit":
            break

    return session.session_key


def main() -> None:
    run_ui(stdin=sys.stdin, stdout=sys.stdout)
