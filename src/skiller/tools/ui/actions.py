from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from skiller.tools.ui.commands import (
    ClearCommand,
    EchoCommand,
    ExitCommand,
    HelpCommand,
    InputCommand,
    LogsCommand,
    ResumeCommand,
    RunCommand,
    RunsCommand,
    SessionCommand,
    StatusCommand,
    UiCommand,
    WatchCommand,
    WebhooksCommand,
)
from skiller.tools.ui.session import UiRun, UiSession


class RuntimeAdapter(Protocol):
    def run(self, *, raw_args: str) -> dict[str, object]: ...
    def runs(self, *, statuses: list[str] | None = None) -> list[dict[str, object]]: ...
    def webhooks(self) -> list[dict[str, object]]: ...
    def status(self, *, run_id: str) -> dict[str, object]: ...
    def logs(self, *, run_id: str) -> list[dict[str, object]]: ...
    def watch(self, *, run_id: str) -> dict[str, object]: ...
    def input_receive(self, *, run_id: str, text: str) -> dict[str, object]: ...
    def resume(self, *, run_id: str) -> dict[str, object]: ...


@dataclass(frozen=True)
class ActionResult:
    kind: str
    message: str | None = None
    run: UiRun | None = None
    runs: list[dict[str, object]] | None = None
    webhooks: list[dict[str, object]] | None = None
    payload: dict[str, object] | None = None
    logs: list[dict[str, object]] | None = None


def handle_command(
    *,
    session: UiSession,
    command: UiCommand,
    runtime: RuntimeAdapter,
) -> ActionResult:
    if command is None:
        return ActionResult(kind="noop")

    if isinstance(command, ExitCommand):
        return ActionResult(kind="exit")

    if isinstance(command, HelpCommand):
        return ActionResult(kind="help")

    if isinstance(command, SessionCommand):
        return ActionResult(kind="session")

    if isinstance(command, RunsCommand):
        return _handle_runs_command(session=session, command=command, runtime=runtime)

    if isinstance(command, WebhooksCommand):
        return ActionResult(kind="webhooks", webhooks=runtime.webhooks())

    if isinstance(command, ClearCommand):
        return ActionResult(kind="clear")

    if isinstance(command, EchoCommand):
        return ActionResult(kind="echo", message=command.message)

    if isinstance(command, RunCommand):
        return _handle_run_command(session=session, command=command, runtime=runtime)

    if isinstance(command, StatusCommand):
        return _handle_status_command(session=session, command=command, runtime=runtime)

    if isinstance(command, LogsCommand):
        return _handle_logs_command(session=session, command=command, runtime=runtime)

    if isinstance(command, WatchCommand):
        return _handle_watch_command(session=session, command=command, runtime=runtime)

    if isinstance(command, ResumeCommand):
        return _handle_resume_command(session=session, command=command, runtime=runtime)

    if isinstance(command, InputCommand):
        return _handle_input_command(session=session, command=command, runtime=runtime)

    raise RuntimeError(f"Unsupported UI command: {type(command).__name__}")


def _handle_run_command(
    *,
    session: UiSession,
    command: RunCommand,
    runtime: RuntimeAdapter,
) -> ActionResult:
    run = UiRun(raw_args=command.raw_args)
    session.runs.append(run)

    try:
        payload = runtime.run(raw_args=command.raw_args)
        if not isinstance(payload, dict):
            raise RuntimeError("run command returned invalid payload")
        run_id = str(payload.get("run_id", "")).strip()
        if not run_id:
            raise RuntimeError("run command returned invalid payload: missing run_id")
        run.run_id = run_id
        run.status = str(payload.get("status", "UNKNOWN"))
        run.last_payload = dict(payload)
        session.remember_run(run)
    except RuntimeError as exc:
        run.status = "FAILED"
        run.error = str(exc)

    return ActionResult(kind="run", run=run)


def _handle_status_command(
    *,
    session: UiSession,
    command: StatusCommand,
    runtime: RuntimeAdapter,
) -> ActionResult:
    payload = runtime.status(run_id=command.run_id)
    payload_dict = dict(payload)
    run_id = str(payload_dict.get("id", command.run_id)).strip() or command.run_id
    raw_args = str(payload_dict.get("skill_ref", "<external>"))
    run = session.ensure_run(run_id, raw_args=raw_args)
    run.raw_args = raw_args or run.raw_args
    run.status = str(payload_dict.get("status", run.status))
    run.last_payload = payload_dict
    session.remember_run(run)
    return ActionResult(kind="status", payload=payload_dict, run=run)


def _handle_runs_command(
    *,
    session: UiSession,
    command: RunsCommand,
    runtime: RuntimeAdapter,
) -> ActionResult:
    normalized_statuses = [status.strip().upper() for status in command.statuses if status.strip()]
    payload = runtime.runs(statuses=normalized_statuses)
    for item in payload:
        run_id = str(item.get("id", "")).strip()
        if not run_id:
            continue
        raw_args = str(item.get("skill_ref", "<external>"))
        run = session.ensure_run(run_id, raw_args=raw_args)
        run.raw_args = raw_args or run.raw_args
        run.status = str(item.get("status", run.status))
        run.last_payload = dict(item)
    return ActionResult(kind="runs", runs=payload)


def _handle_logs_command(
    *,
    session: UiSession,
    command: LogsCommand,
    runtime: RuntimeAdapter,
) -> ActionResult:
    logs = runtime.logs(run_id=command.run_id)
    run = session.ensure_run(command.run_id)
    run.logs = list(logs)
    session.remember_run(run)
    return ActionResult(kind="logs", logs=logs, run=run)


def _handle_watch_command(
    *,
    session: UiSession,
    command: WatchCommand,
    runtime: RuntimeAdapter,
) -> ActionResult:
    payload = runtime.watch(run_id=command.run_id)
    payload_dict = dict(payload)
    run_id = str(payload_dict.get("run_id", command.run_id)).strip() or command.run_id
    run = session.ensure_run(run_id)
    run.status = str(payload_dict.get("status", run.status))
    run.last_payload = payload_dict
    session.remember_run(run)
    return ActionResult(kind="watch", payload=payload_dict, run=run)


def _handle_resume_command(
    *,
    session: UiSession,
    command: ResumeCommand,
    runtime: RuntimeAdapter,
) -> ActionResult:
    payload = runtime.resume(run_id=command.run_id)
    payload_dict = dict(payload)
    run = session.ensure_run(command.run_id)
    run.status = str(payload_dict.get("status", run.status))
    run.last_payload = payload_dict
    session.remember_run(run)
    return ActionResult(kind="resume", payload=payload_dict, run=run)


def _handle_input_command(
    *,
    session: UiSession,
    command: InputCommand,
    runtime: RuntimeAdapter,
) -> ActionResult:
    payload = runtime.input_receive(run_id=command.run_id, text=command.text)
    payload_dict = dict(payload)
    run = session.ensure_run(command.run_id)
    run.last_payload = payload_dict
    session.remember_run(run)
    return ActionResult(kind="input", payload=payload_dict, run=run)
