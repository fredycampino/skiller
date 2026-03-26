from __future__ import annotations

import json
from typing import TextIO

from skiller.tools.ui.actions import ActionResult
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
    stdout.write("Commands:\n")
    stdout.write("  /help                      Show this help\n")
    stdout.write("  /session                   Show known runs and current selection\n")
    stdout.write("  /runs                      Show recent persisted runs\n")
    stdout.write("  /webhooks                  Show registered webhook channels\n")
    stdout.write("  /clear                     Clear the screen\n")
    stdout.write("  /run <args>                Run a skill, for example: /run notify_test\n")
    stdout.write(
        "  /run --file <path>         Run a skill file, for example: "
        "/run --file skill.yaml\n"
    )
    stdout.write("  /status <run_id>           Show run status\n")
    stdout.write("  /logs <run_id>             Show recent run logs\n")
    stdout.write("  /watch <run_id>            Watch a run until it stops\n")
    stdout.write("  /input <run_id> <text>     Send text to a waiting input step\n")
    stdout.write("  /resume <run_id>           Resume a waiting run\n")
    stdout.write("  /exit                      Exit the UI\n")
    stdout.flush()


def write_session(*, stdout: TextIO, session: UiSession) -> None:
    stdout.write(f"session_key: {session.session_key}\n")
    stdout.write(f"selected_run_id: {session.selected_run_id or '-'}\n")
    stdout.write(f"last_run_id: {session.last_run_id or '-'}\n")
    write_runs_table(stdout=stdout, session=session)
    write_selected_run_detail(stdout=stdout, session=session)
    stdout.flush()


def write_clear(*, stdout: TextIO) -> None:
    stdout.write("\033[2J\033[H")
    stdout.flush()


def write_run_result(*, stdout: TextIO, session: UiSession, run: UiRun) -> None:
    _ = session
    args_label = run.raw_args or "<empty>"
    waiting_metadata = _get_waiting_metadata(run.last_payload) if run.status == "WAITING" else None
    if waiting_metadata is not None:
        stdout.write(f"run_id: {_display_run_id(run)}\n")
        stdout.write(f"args: {args_label}\n")
        stdout.write(f"status: WAITING {waiting_metadata['wait_type']}\n")
        _write_waiting_metadata(stdout=stdout, metadata=waiting_metadata)
    else:
        stdout.write(f"run_id: {_display_run_id(run)} status: {run.status} args: {args_label}\n")
    if run.error:
        stdout.write(f"error: {run.error}\n")
    stdout.flush()


def write_runs_table(*, stdout: TextIO, session: UiSession) -> None:
    if not session.runs:
        stdout.write("runs: []\n")
        return

    for index, run in enumerate(session.runs, start=1):
        args_label = run.raw_args or "<empty>"
        error_label = f" error={run.error}" if run.error else ""
        selected_label = " *" if run.run_id and run.run_id == session.selected_run_id else ""
        stdout.write(
            f"runs[{index}]: {_display_run_id(run)} "
            f"{run.status}{selected_label} {args_label}{error_label}\n"
        )


def write_selected_run_detail(*, stdout: TextIO, session: UiSession) -> None:
    if session.selected_run_id is None:
        return

    run = session.find_run(session.selected_run_id)
    if run is None:
        return

    stdout.write(
        f"selected: run_id: {_display_run_id(run)} "
        f"status: {run.status} args: {run.raw_args or '<empty>'}\n"
    )
    if run.last_payload:
        stdout.write(f"last_payload: {_render_json(run.last_payload)}\n")
    if run.logs:
        stdout.write("recent_logs:\n")
        for index, event in enumerate(run.logs[-3:], start=1):
            stdout.write(f"  [{index}] {_render_log_event(event)}\n")
    if run.status == "WAITING" and run.run_id:
        _write_waiting_hints(stdout=stdout, run=run)


def write_bye(*, stdout: TextIO) -> None:
    stdout.write("bye\n")
    stdout.flush()


def render_action_result(*, stdout: TextIO, session: UiSession, result: ActionResult) -> None:
    if result.kind == "noop":
        return
    if result.kind == "echo":
        write_echo(stdout=stdout, session=session, message=result.message or "")
        return
    if result.kind == "help":
        write_help(stdout=stdout)
        return
    if result.kind == "session":
        write_session(stdout=stdout, session=session)
        return
    if result.kind == "runs":
        write_global_runs(stdout=stdout, result=result)
        return
    if result.kind == "webhooks":
        write_webhooks(stdout=stdout, result=result)
        return
    if result.kind == "clear":
        write_clear(stdout=stdout)
        return
    if result.kind == "run":
        if result.run is None:
            raise RuntimeError("render_action_result requires run for kind 'run'")
        write_run_result(stdout=stdout, session=session, run=result.run)
        if result.run.status == "WAITING" and result.run.run_id:
            _write_waiting_hints(stdout=stdout, run=result.run)
            stdout.flush()
        return
    if result.kind == "status":
        write_status_result(stdout=stdout, result=result)
        return
    if result.kind == "watch":
        write_watch_result(stdout=stdout, result=result)
        return
    if result.kind == "resume":
        write_resume_result(stdout=stdout, result=result)
        return
    if result.kind == "input":
        write_input_result(stdout=stdout, result=result)
        stdout.flush()
        return
    if result.kind == "logs":
        write_logs_result(stdout=stdout, result=result)
        return
    if result.kind == "exit":
        write_bye(stdout=stdout)
        return
    raise RuntimeError(f"Unsupported action result kind '{result.kind}'")


def _display_run_id(run: UiRun) -> str:
    if run.run_id is None:
        return "-"
    return run.run_id


def write_status_result(*, stdout: TextIO, result: ActionResult) -> None:
    if result.run is None:
        raise RuntimeError("status result requires run")
    waiting_metadata = _get_waiting_metadata(result.run.last_payload)
    if result.run.status == "WAITING" and waiting_metadata is not None:
        stdout.write(f"run_id: {_display_run_id(result.run)}\n")
        stdout.write(f"args: {result.run.raw_args or '<empty>'}\n")
        stdout.write(f"status: WAITING {waiting_metadata['wait_type']}\n")
        _write_waiting_metadata(stdout=stdout, metadata=waiting_metadata)
        _write_waiting_hints(stdout=stdout, run=result.run)
    else:
        stdout.write(
            f"status: run_id: {_display_run_id(result.run)} "
            f"status: {result.run.status}\n"
        )
        if result.run.status == "WAITING" and result.run.run_id:
            _write_waiting_hints(stdout=stdout, run=result.run)
    stdout.flush()


def write_watch_result(*, stdout: TextIO, result: ActionResult) -> None:
    if result.run is None:
        raise RuntimeError("watch result requires run")
    payload = result.payload or {}
    stdout.write(
        f"watch: run_id: {_display_run_id(result.run)} "
        f"status: {result.run.status}\n"
    )
    events_text = str(payload.get("events_text", "")).strip()
    if events_text:
        stdout.write(f"events: {events_text}\n")
    stdout.flush()


def write_resume_result(*, stdout: TextIO, result: ActionResult) -> None:
    if result.run is None:
        raise RuntimeError("resume result requires run")
    payload = result.payload or {}
    stdout.write(
        f"resume: run_id: {_display_run_id(result.run)} "
        f"status: {result.run.status}\n"
    )
    if payload:
        stdout.write(f"resume_payload: {_render_json(payload)}\n")
    stdout.flush()


def write_input_result(*, stdout: TextIO, result: ActionResult) -> None:
    if result.run is None:
        raise RuntimeError("input result requires run")
    payload = result.payload or {}
    accepted = payload.get("accepted", False)
    stdout.write(
        f"input: run_id: {_display_run_id(result.run)} "
        f"accepted: {accepted}\n"
    )
    matched_runs = payload.get("matched_runs")
    if matched_runs:
        stdout.write(f"matched_runs: {_render_json(matched_runs)}\n")
    stdout.flush()


def write_logs_result(*, stdout: TextIO, result: ActionResult) -> None:
    logs = result.logs or []
    if result.run is not None:
        stdout.write(f"logs: run_id: {_display_run_id(result.run)} count: {len(logs)}\n")
    else:
        stdout.write(f"logs: count: {len(logs)}\n")
    for index, event in enumerate(logs[-5:], start=1):
        stdout.write(f"  [{index}] {_render_log_event(event)}\n")
    stdout.flush()


def write_global_runs(*, stdout: TextIO, result: ActionResult) -> None:
    runs = result.runs or []
    if not runs:
        stdout.write("runs: []\n")
        stdout.flush()
        return
    stdout.write("runs:\n")
    for item in runs:
        run_id = str(item.get("id", "-"))
        status = str(item.get("status", "UNKNOWN"))
        skill_ref = str(item.get("skill_ref", "<external>"))
        current = str(item.get("current", "-") or "-")
        stdout.write(f"  {run_id}  {status}  {skill_ref}  {current}\n")
    stdout.flush()


def write_webhooks(*, stdout: TextIO, result: ActionResult) -> None:
    webhooks = result.webhooks or []
    if not webhooks:
        stdout.write("webhooks: []\n")
        stdout.flush()
        return
    stdout.write("webhooks:\n")
    for item in webhooks:
        webhook = str(item.get("webhook", "-"))
        enabled = bool(item.get("enabled", False))
        created_at = str(item.get("created_at", "-"))
        stdout.write(f"  {webhook}  enabled={str(enabled).lower()}  created_at={created_at}\n")
    stdout.flush()


def _render_log_event(event: dict[str, object]) -> str:
    event_type = str(event.get("type", "UNKNOWN"))
    payload = event.get("payload")
    if isinstance(payload, dict) and payload:
        return f"{event_type} payload={_render_json(payload)}"
    return event_type


def _render_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True)


def _write_waiting_hints(*, stdout: TextIO, run: UiRun) -> None:
    if run.run_id is None:
        return
    waiting_metadata = _get_waiting_metadata(run.last_payload)
    if waiting_metadata is not None and waiting_metadata["wait_type"] == "input":
        stdout.write(f"next: /input {run.run_id} <text>\n")
    stdout.write(f"next: /watch {run.run_id}\n")


def _write_waiting_metadata(*, stdout: TextIO, metadata: dict[str, str]) -> None:
    if metadata["wait_type"] == "webhook":
        stdout.write(f"webhook: {metadata['webhook']}\n")
        stdout.write(f"key: {metadata['key']}\n")
        return
    if metadata["wait_type"] == "input":
        stdout.write(f"prompt: {metadata['prompt']}\n")


def _get_waiting_metadata(payload: dict[str, object]) -> dict[str, str] | None:
    wait_type = str(payload.get("wait_type", "")).strip().lower()
    if wait_type == "webhook":
        webhook = str(payload.get("webhook", "")).strip()
        key = str(payload.get("key", "")).strip()
        if webhook and key:
            return {"wait_type": "webhook", "webhook": webhook, "key": key}
        return None
    if wait_type == "input":
        prompt = str(payload.get("prompt", "")).strip()
        if prompt:
            return {"wait_type": "input", "prompt": prompt}
        return None
    return None
