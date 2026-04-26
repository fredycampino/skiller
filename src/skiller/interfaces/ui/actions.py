from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from skiller.interfaces.ui.commands import (
    BodyCommand,
    ClearCommand,
    EchoCommand,
    ExitCommand,
    HelpCommand,
    InputCommand,
    LogsCommand,
    ResumeCommand,
    RunCommand,
    RunsCommand,
    ServerStatusCommand,
    SessionCommand,
    StatusCommand,
    UiCommand,
    WatchCommand,
    WebhooksCommand,
)
from skiller.interfaces.ui.session import UiRun, UiSession


class RuntimeAdapter(Protocol):
    def run(self, *, raw_args: str) -> dict[str, object]: ...
    def server_status(self) -> dict[str, object]: ...
    def runs(self, *, statuses: list[str] | None = None) -> list[dict[str, object]]: ...
    def webhooks(self) -> list[dict[str, object]]: ...
    def status(self, *, run_id: str) -> dict[str, object]: ...
    def logs(self, *, run_id: str) -> list[dict[str, object]]: ...
    def get_execution_output(self, *, body_ref: str) -> dict[str, object] | None: ...
    def watch(self, *, run_id: str) -> dict[str, object]: ...
    def input_receive(self, *, run_id: str, text: str) -> dict[str, object]: ...
    def resume(self, *, run_id: str) -> dict[str, object]: ...


@dataclass(frozen=True)
class ActionResult:
    kind: str
    message: str | None = None
    run: UiRun | None = None
    runs: list[dict[str, object]] | None = None
    statuses: list[str] | None = None
    webhooks: list[dict[str, object]] | None = None
    payload: dict[str, object] | None = None
    logs: list[dict[str, object]] | None = None
    body_ref: str | None = None


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

    if isinstance(command, ServerStatusCommand):
        return ActionResult(kind="server", payload=runtime.server_status())

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

    if isinstance(command, BodyCommand):
        return _handle_body_command(command=command, runtime=runtime)

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
        run.has_rendered_create_block = True
        if run.status.upper() in {"SUCCEEDED", "FAILED"}:
            run.logs = _resolve_log_body_refs(logs=runtime.logs(run_id=run_id), runtime=runtime)
            _remember_seen_event_ids(run=run, events=run.logs)
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
    payload_dict = _resolve_status_body_refs(payload=dict(payload), runtime=runtime)
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
    return ActionResult(kind="runs", runs=payload, statuses=normalized_statuses)


def _handle_logs_command(
    *,
    session: UiSession,
    command: LogsCommand,
    runtime: RuntimeAdapter,
) -> ActionResult:
    run_id = _resolve_optional_run_id(
        session=session,
        requested_run_id=command.run_id,
    )
    if run_id is None:
        return ActionResult(
            kind="logs",
            run=UiRun(
                raw_args="logs",
                status="FAILED",
                error="No selected or last run is available for /logs",
            ),
            logs=[],
        )

    logs = _resolve_log_body_refs(logs=runtime.logs(run_id=run_id), runtime=runtime)
    run = session.ensure_run(run_id)
    run.logs = list(logs)
    session.remember_run(run)
    return ActionResult(kind="logs", logs=logs, run=run)


def _handle_body_command(
    *,
    command: BodyCommand,
    runtime: RuntimeAdapter,
) -> ActionResult:
    body_ref = command.body_ref.strip()
    if not body_ref:
        return ActionResult(
            kind="body",
            run=UiRun(raw_args="body", status="FAILED", error="body_ref is required for /body"),
        )

    payload = runtime.get_execution_output(body_ref=body_ref)
    if payload is None:
        return ActionResult(
            kind="body",
            run=UiRun(
                raw_args="body",
                status="FAILED",
                error=f"Execution output not found for {body_ref}",
            ),
            body_ref=body_ref,
        )

    return ActionResult(
        kind="body",
        payload=dict(payload),
        body_ref=body_ref,
    )


def _handle_watch_command(
    *,
    session: UiSession,
    command: WatchCommand,
    runtime: RuntimeAdapter,
) -> ActionResult:
    payload = runtime.watch(run_id=command.run_id)
    payload_dict = _resolve_watch_body_refs(payload=dict(payload), runtime=runtime)
    return _build_watch_action_result(
        session=session,
        run_id=command.run_id,
        payload_dict=payload_dict,
    )


def poll_run_progress(
    *,
    session: UiSession,
    run_id: str,
    runtime: RuntimeAdapter,
) -> ActionResult:
    status_payload = runtime.status(run_id=run_id)
    payload_dict = _resolve_status_body_refs(payload=dict(status_payload), runtime=runtime)
    resolved_run_id = str(payload_dict.get("id", run_id)).strip() or run_id
    payload_dict["run_id"] = resolved_run_id
    payload_dict["events"] = _resolve_log_body_refs(
        logs=runtime.logs(run_id=resolved_run_id),
        runtime=runtime,
    )
    raw_args = str(payload_dict.get("skill_ref", "")).strip() or None
    return _build_watch_action_result(
        session=session,
        run_id=resolved_run_id,
        payload_dict=payload_dict,
        raw_args=raw_args,
    )


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


def _resolve_status_body_refs(
    *,
    payload: dict[str, object],
    runtime: RuntimeAdapter,
) -> dict[str, object]:
    context = payload.get("context")
    if not isinstance(context, dict):
        return payload

    step_executions = context.get("step_executions")
    if not isinstance(step_executions, dict):
        return payload

    resolved_step_executions: dict[str, object] = {}
    for step_id, execution in step_executions.items():
        if not isinstance(step_id, str) or not isinstance(execution, dict):
            resolved_step_executions[step_id] = execution
            continue
        resolved_step_executions[step_id] = _resolve_execution_output_body(
            execution=execution,
            runtime=runtime,
        )

    resolved_context = dict(context)
    resolved_context["step_executions"] = resolved_step_executions
    resolved_payload = dict(payload)
    resolved_payload["context"] = resolved_context
    return resolved_payload


def _build_watch_action_result(
    *,
    session: UiSession,
    run_id: str,
    payload_dict: dict[str, object],
    raw_args: str | None = None,
) -> ActionResult:
    resolved_run_id = str(payload_dict.get("run_id", run_id)).strip() or run_id
    run = session.ensure_run(resolved_run_id, raw_args=raw_args or "<external>")
    if raw_args:
        run.raw_args = raw_args

    events = payload_dict.get("events")
    normalized_payload = dict(payload_dict)
    if isinstance(events, list):
        run.logs = [dict(item) for item in events if isinstance(item, dict)]
        normalized_payload["events"] = _filter_fresh_watch_events(run=run, events=events)

    run.status = str(normalized_payload.get("status", run.status))
    run.last_payload = normalized_payload
    session.remember_run(run)
    return ActionResult(kind="watch", payload=normalized_payload, run=run)


def _filter_fresh_watch_events(
    *,
    run: UiRun,
    events: list[object],
) -> list[dict[str, object]]:
    fresh_events: list[dict[str, object]] = []
    for item in events:
        if not isinstance(item, dict):
            continue
        event_dict = dict(item)
        event_name = str(event_dict.get("type", "")).strip().upper()
        if event_name == "RUN_CREATE" and run.has_rendered_create_block:
            _remember_seen_event_ids(run=run, events=[event_dict])
            continue

        event_id = str(event_dict.get("id", "")).strip()
        if event_id:
            if event_id in run.seen_event_ids:
                continue
            run.seen_event_ids.add(event_id)
        fresh_events.append(event_dict)
    return fresh_events


def _remember_seen_event_ids(*, run: UiRun, events: list[object]) -> None:
    for item in events:
        if not isinstance(item, dict):
            continue
        event_id = str(item.get("id", "")).strip()
        if event_id:
            run.seen_event_ids.add(event_id)


def _resolve_log_body_refs(
    *,
    logs: list[dict[str, object]],
    runtime: RuntimeAdapter,
) -> list[dict[str, object]]:
    return [_resolve_event_body_refs(event=event, runtime=runtime) for event in logs]


def _resolve_watch_body_refs(
    *,
    payload: dict[str, object],
    runtime: RuntimeAdapter,
) -> dict[str, object]:
    events = payload.get("events")
    if not isinstance(events, list):
        return payload

    resolved_payload = dict(payload)
    resolved_payload["events"] = [
        _resolve_event_body_refs(event=event, runtime=runtime)
        for event in events
        if isinstance(event, dict)
    ]
    return resolved_payload


def _resolve_event_body_refs(
    *,
    event: dict[str, object],
    runtime: RuntimeAdapter,
) -> dict[str, object]:
    payload = event.get("payload")
    if not isinstance(payload, dict):
        return dict(event)

    resolved_payload = _resolve_event_payload_output(payload=payload, runtime=runtime)
    resolved_event = dict(event)
    resolved_event["payload"] = resolved_payload
    return resolved_event


def _resolve_event_payload_output(
    *,
    payload: dict[str, object],
    runtime: RuntimeAdapter,
) -> dict[str, object]:
    step_type = str(payload.get("step_type", "")).strip().lower()
    if step_type != "llm_prompt":
        return dict(payload)

    output = payload.get("output")
    if not isinstance(output, dict):
        return dict(payload)

    resolved_output = _resolve_output_body(output=output, runtime=runtime)
    resolved_payload = dict(payload)
    resolved_payload["output"] = resolved_output
    return resolved_payload


def _resolve_execution_output_body(
    *,
    execution: dict[str, object],
    runtime: RuntimeAdapter,
) -> dict[str, object]:
    step_type = str(execution.get("step_type", "")).strip().lower()
    if step_type != "llm_prompt":
        return dict(execution)

    output = execution.get("output")
    if not isinstance(output, dict):
        return dict(execution)

    resolved_execution = dict(execution)
    resolved_execution["output"] = _resolve_output_body(output=output, runtime=runtime)
    return resolved_execution


def _resolve_output_body(
    *,
    output: dict[str, object],
    runtime: RuntimeAdapter,
) -> dict[str, object]:
    text_ref = str(output.get("text_ref", "")).strip()
    body_ref = str(output.get("body_ref", "")).strip()
    if not body_ref:
        return dict(output)

    output_body = _get_execution_output_body(runtime=runtime, body_ref=body_ref)
    if not isinstance(output_body, dict):
        return dict(output)

    resolved_output = dict(output)
    body_value = output_body.get("value")
    if isinstance(body_value, dict):
        resolved_output["value"] = body_value
        resolved_text = _resolve_text_ref(value=body_value, text_ref=text_ref)
        if resolved_text is not None:
            resolved_output["text"] = resolved_text
    return resolved_output


def _get_execution_output_body(
    *,
    runtime: RuntimeAdapter,
    body_ref: str,
) -> dict[str, Any] | None:
    getter = getattr(runtime, "get_execution_output", None)
    if getter is None:
        return None
    payload = getter(body_ref=body_ref)
    return payload if isinstance(payload, dict) else None


def _resolve_text_ref(*, value: dict[str, object], text_ref: str) -> str | None:
    if not text_ref:
        return None

    current: object = value
    for part in text_ref.split("."):
        key = part.strip()
        if not key:
            return None
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]

    if isinstance(current, str):
        return current
    if isinstance(current, (int, float, bool)) or current is None:
        return str(current)
    return None


def _resolve_optional_run_id(
    *,
    session: UiSession,
    requested_run_id: str,
) -> str | None:
    run_id = requested_run_id.strip()
    if run_id:
        return run_id
    if session.selected_run_id:
        return session.selected_run_id
    if session.last_run_id:
        return session.last_run_id
    return None
