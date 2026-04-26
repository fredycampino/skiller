from __future__ import annotations

import json
import re
import shlex
import textwrap
import time
from codecs import decode as codecs_decode
from dataclasses import dataclass
from pathlib import Path

from skiller.interfaces.ui.actions import ActionResult
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
    iter_help_lines,
)
from skiller.interfaces.ui.session import UiRun, UiSession
from skiller.interfaces.ui.theme import theme


@dataclass(frozen=True)
class BufferRenderResult:
    text: str
    replace: bool = False


_SPINNER_FRAMES = ("◐", "◓", "◑", "◒")
_EXCEPTION_LINE_RE = re.compile(
    r"^(?P<kind>[A-Za-z_][\w.]*(?:Error|Exception|Warning)?):\s*(?P<message>.+)$"
)
_DETAIL_WRAP_WIDTH = 72


def build_initial_output(*, session: UiSession) -> str:
    _ = session
    return ""


def render_result_for_buffer(
    *,
    session: UiSession,
    result: ActionResult,
) -> BufferRenderResult:
    if result.kind == "noop":
        return BufferRenderResult(text="")
    if result.kind == "clear":
        return BufferRenderResult(text="", replace=True)
    return BufferRenderResult(text=_render_action_result(session=session, result=result))


def _build_header_line(*, left: str, right: str, left_width: int = 42) -> str:
    return f"{left:<{left_width}}{right}"


def build_header_title_line(*, session: UiSession) -> str:
    return _build_header_line(left="[ Skiller ]", right=f"session: {session.session_key}")


def build_header_meta_line(*, session: UiSession) -> str:
    selected = session.selected_run_id or "-"
    return _build_header_line(left="Run Console", right=f"selected: {selected}")


def build_pending_status_text(*, command: UiCommand) -> str:
    if command is None:
        return "Idle"
    if isinstance(command, RunCommand):
        return f"Running {_build_run_label_from_raw_args(command.raw_args)}"
    if isinstance(command, ServerStatusCommand):
        return "Loading server"
    if isinstance(command, WatchCommand):
        return "Watching"
    if isinstance(command, LogsCommand):
        return "Loading logs"
    if isinstance(command, BodyCommand):
        return "Loading body"
    if isinstance(command, RunsCommand):
        return "Loading runs"
    if isinstance(command, StatusCommand):
        return "Loading status"
    if isinstance(command, WebhooksCommand):
        return "Loading webhooks"
    if isinstance(command, InputCommand):
        return "Sending input"
    if isinstance(command, ResumeCommand):
        return "Resuming"
    if isinstance(command, HelpCommand):
        return "Loading help"
    if isinstance(command, SessionCommand):
        return "Loading session"
    if isinstance(command, ClearCommand):
        return "Clearing"
    if isinstance(command, EchoCommand):
        return "Sending message"
    if isinstance(command, ExitCommand):
        return "Closing"
    return "Processing"


def build_pending_input_status_text(*, run: UiRun | None) -> str:
    if run is None:
        return "Running"
    return f"Running {_build_run_label(run)}"


def build_result_status_text(*, result: ActionResult) -> str:
    if result.kind == "noop":
        return "Idle"
    if result.kind == "clear":
        return "Cleared"
    if result.kind in {"echo", "help", "session"}:
        return "Ready"
    if result.kind == "runs":
        return _build_loaded_label("run", len(result.runs or []))
    if result.kind == "server":
        return "Loaded server"
    if result.kind == "webhooks":
        return _build_loaded_label("webhook", len(result.webhooks or []))
    if result.kind == "logs":
        if result.run is not None and (result.run.error or result.run.status.upper() == "FAILED"):
            return "Error"
        return f"Loaded logs {_build_run_ref(result.run)}"
    if result.kind == "body":
        if result.run is not None and (result.run.error or result.run.status.upper() == "FAILED"):
            return "Error"
        return "Loaded body"
    if result.kind == "input":
        payload = result.payload or {}
        error = str(payload.get("error", "")).strip()
        if error:
            return "Error"
        return f"Input sent {_build_run_ref(result.run)}"
    if result.kind == "resume":
        return _build_run_status_label(result.run)
    if result.kind in {"run", "status", "watch"}:
        return _build_run_status_label(result.run)
    if result.kind == "exit":
        return "Closing"
    return "Ready"


def _build_loaded_label(noun: str, count: int) -> str:
    suffix = noun if count == 1 else f"{noun}s"
    return f"Loaded {count} {suffix}"


def _build_run_ref(run: UiRun | None) -> str:
    if run is None:
        return "-"
    return run.run_id or "-"


def _build_run_status_label(run: UiRun | None, *, waiting_label: str = "waiting") -> str:
    if run is None:
        return "Ready"

    status = run.status.upper()
    if run.error or status == "FAILED":
        return "Error"
    if status == "WAITING":
        waiting_metadata = _get_waiting_metadata(run.last_payload)
        if waiting_metadata is not None:
            if waiting_metadata["wait_type"] == "input":
                return "Waiting → input"
            if waiting_metadata["wait_type"] == "webhook":
                return "Waiting → webhook"
        return f"{waiting_label.title()} {_build_run_label(run)}"
    if status == "RUNNING":
        return f"Running {_build_run_label(run)}"
    if status == "SUCCEEDED":
        return f"Success {_build_run_label(run)}"
    if status == "CREATED":
        return f"Created {_build_run_label(run)}"
    if status:
        return f"{status.title()} {_build_run_label(run)}"
    return f"Ready {_build_run_label(run)}"


def _build_run_label(run: UiRun) -> str:
    return _build_run_label_from_raw_args(run.raw_args, fallback=_build_run_ref(run))


def _build_run_label_from_raw_args(raw_args: str, *, fallback: str = "-") -> str:
    normalized = raw_args.strip()
    if not normalized:
        return fallback

    try:
        parts = shlex.split(normalized)
    except ValueError:
        return normalized

    if not parts:
        return fallback
    if parts[0] == "--file" and len(parts) > 1:
        return parts[1]
    return parts[0]


def _build_run_error_message(run: UiRun) -> str:
    if run.error:
        event_error = _extract_error_field(run.error)
        if event_error:
            return event_error
        extracted = _extract_concise_error_message(run.error)
        if extracted:
            return extracted

    payload = run.last_payload
    error = str(payload.get("error", "")).strip()
    if error:
        extracted = _extract_concise_error_message(error)
        if extracted:
            return extracted

    return _build_run_label(run)


def _extract_error_field(raw_text: str) -> str | None:
    for line in reversed(raw_text.splitlines()):
        normalized = line.strip()
        if "error=" not in normalized:
            continue
        raw_error = normalized.split("error=", 1)[1].strip()
        if not raw_error:
            continue
        try:
            parsed_error = json.loads(raw_error)
        except json.JSONDecodeError:
            extracted = _extract_concise_error_message(raw_error)
            return extracted or raw_error
        parsed = str(parsed_error).strip()
        extracted = _extract_concise_error_message(parsed)
        return extracted or parsed or None
    return None


def _extract_concise_error_message(raw_error: str) -> str | None:
    normalized = raw_error.strip()
    if not normalized:
        return None

    lines = [line.strip() for line in normalized.splitlines() if line.strip()]
    if not lines:
        return None

    for line in reversed(lines):
        match = _EXCEPTION_LINE_RE.match(line)
        if match is None:
            continue
        message = match.group("message").strip()
        if message:
            return message
        kind = match.group("kind").strip()
        if kind:
            return kind

    return lines[-1]


def build_status_line(
    *,
    session: UiSession,
    status_text: str = "Idle",
    busy: bool = False,
    now: float | None = None,
) -> str:
    _ = session
    if busy or _should_show_progress(status_text):
        current_time = time.monotonic() if now is None else now
        frame = _SPINNER_FRAMES[int(current_time * 10) % len(_SPINNER_FRAMES)]
        return f"{frame} {status_text}"
    if status_text == "Idle":
        return "· Idle"
    if status_text.startswith("Waiting "):
        return f"◌ {status_text}"
    if status_text.startswith("Success "):
        return f"✓ {status_text}"
    if status_text == "Error" or status_text.startswith("Error "):
        return f"× {status_text}"
    return status_text


def _should_show_progress(status_text: str) -> bool:
    return status_text.startswith("Loading ") or status_text.startswith("Running ")


def build_footer_line(*, session: UiSession) -> str:
    last = session.last_run_id or "-"
    return f"  last={last} | Enter command | Ctrl+C exit"


def _render_action_result(*, session: UiSession, result: ActionResult) -> str:
    if result.kind == "echo":
        return f"[{session.session_key}] echo: {result.message or ''}\n"
    if result.kind == "help":
        return _render_help()
    if result.kind == "session":
        return _render_session(session=session)
    if result.kind == "server":
        return _render_server_result(result=result)
    if result.kind == "runs":
        return _render_global_runs(result=result)
    if result.kind == "webhooks":
        return _render_webhooks(result=result)
    if result.kind == "run":
        if result.run is None:
            raise RuntimeError("render_action_result requires run for kind 'run'")
        return _render_run_result(result=result)
    if result.kind == "status":
        return _render_status_result(result=result)
    if result.kind == "watch":
        return _render_watch_result(result=result)
    if result.kind == "resume":
        return _render_resume_result(result=result)
    if result.kind == "input":
        return _render_input_result(result=result)
    if result.kind == "logs":
        return _render_logs_result(result=result)
    if result.kind == "body":
        return _render_body_result(result=result)
    if result.kind == "exit":
        return "bye\n"
    raise RuntimeError(f"Unsupported action result kind '{result.kind}'")


def _render_help() -> str:
    lines = ["Commands:\n"]
    for line in iter_help_lines():
        lines.append(f"{line}\n")
    return "".join(lines)


def _render_session(*, session: UiSession) -> str:
    lines = [
        f"session_key: {session.session_key}\n",
        f"selected_run_id: {session.selected_run_id or '-'}\n",
        f"last_run_id: {session.last_run_id or '-'}\n",
    ]
    lines.extend(_render_runs_table(session=session))
    lines.extend(_render_selected_run_detail(session=session))
    return "".join(lines)


def _render_run_result(*, result: ActionResult) -> str:
    run = result.run
    if run is None:
        raise RuntimeError("run result requires run")
    waiting_metadata = _get_waiting_metadata(run.last_payload) if run.status == "WAITING" else None
    lines: list[str] = []
    if waiting_metadata is not None:
        lines.extend(_build_run_create_block(run=run, metadata=waiting_metadata))
        return _join_output_block(lines)

    create_header = _build_execution_block_header(run, kind="run-create")
    if run.logs:
        lines.extend(
            _build_watch_blocks_from_events(
                run=run,
                events=run.logs,
                block_kind="run-create",
            )
        )
        return _join_output_block(lines)

    if run.error or run.status.upper() == "FAILED":
        lines.extend(_build_error_block(run=run, header=create_header))
        return _join_output_block(lines)

    if run.status.upper() == "SUCCEEDED":
        lines.extend(_build_success_block(run=run, header=create_header))
        return _join_output_block(lines)

    lines.extend(
        _build_run_summary_block(
            run=run,
            label=run.status.title(),
            header=_build_execution_block_header(run, kind="run-create"),
        )
    )
    return _join_output_block(lines)


def _render_runs_table(*, session: UiSession) -> list[str]:
    if not session.runs:
        return ["runs: []\n"]

    lines: list[str] = []
    for index, run in enumerate(session.runs, start=1):
        args_label = run.raw_args or "<empty>"
        error_label = f" error={run.error}" if run.error else ""
        selected_label = " *" if run.run_id and run.run_id == session.selected_run_id else ""
        lines.append(
            f"runs[{index}]: {_display_run_id(run)} "
            f"{run.status}{selected_label} {args_label}{error_label}\n"
        )
    return lines


def _render_selected_run_detail(*, session: UiSession) -> list[str]:
    if session.selected_run_id is None:
        return []

    run = session.find_run(session.selected_run_id)
    if run is None:
        return []

    lines = [
        f"selected: run_id: {_display_run_id(run)} "
        f"status: {run.status} args: {run.raw_args or '<empty>'}\n"
    ]
    if run.last_payload:
        lines.append(f"last_payload: {_render_json(run.last_payload)}\n")
    if run.logs:
        lines.append("recent_logs:\n")
        for index, event in enumerate(run.logs[-3:], start=1):
            lines.append(f"  [{index}] {_render_pretty_json(event)}\n")
    if run.status == "WAITING" and run.run_id:
        lines.extend(_render_waiting_hints(run=run))
    return lines


def _render_status_result(*, result: ActionResult) -> str:
    if result.run is None:
        raise RuntimeError("status result requires run")
    waiting_metadata = _get_waiting_metadata(result.run.last_payload)
    if result.run.status == "WAITING" and waiting_metadata is not None:
        return _join_output_block(_build_waiting_block(run=result.run, metadata=waiting_metadata))

    if result.run.status.upper() == "SUCCEEDED":
        return _join_output_block(_build_success_block(run=result.run))

    if result.run.error or result.run.status.upper() == "FAILED":
        return _join_output_block(_build_error_block(run=result.run))

    return _join_output_block(
        _build_run_summary_block(run=result.run, label=result.run.status.title())
    )


def _render_watch_result(*, result: ActionResult) -> str:
    if result.run is None:
        raise RuntimeError("watch result requires run")
    payload = result.payload or result.run.last_payload
    events = payload.get("events")
    if isinstance(events, list):
        lines = _build_watch_blocks_from_events(run=result.run, events=events)
        if lines:
            return _join_output_block(lines)
    return _join_output_block(_build_run_summary_block(run=result.run, label="Watch"))


def _render_resume_result(*, result: ActionResult) -> str:
    if result.run is None:
        raise RuntimeError("resume result requires run")
    payload = result.payload or {}
    events = payload.get("events")
    header_kind = (
        _infer_execution_block_kind(events) if isinstance(events, list) else "run-resume"
    )
    lines = _build_run_summary_block(
        run=result.run,
        label="Resume",
        header=_build_execution_block_header(result.run, kind=header_kind),
    )
    if payload:
        lines.append(f"payload: {_render_json(payload)}")
    return _join_output_block(lines)


def _render_input_result(*, result: ActionResult) -> str:
    if result.run is None:
        raise RuntimeError("input result requires run")
    payload = result.payload or {}
    state = "input accepted" if payload.get("accepted", False) else "input rejected"
    lines = [_build_run_block_header(result.run), f"  ↳ {state}"]
    matched_runs = payload.get("matched_runs")
    if matched_runs:
        lines.append(f"    matched: {_render_json(matched_runs)}")
    error = str(payload.get("error", "")).strip()
    if error:
        lines.append(f"    {error}")
    return _join_output_block(lines)


def _render_logs_result(*, result: ActionResult) -> str:
    logs = result.logs or []
    run = result.run if result.run is not None else UiRun(raw_args="<external>")
    if run.error:
        return _join_output_block(_build_error_block(run=run))
    lines: list[str] = [_build_run_block_header(run), "  ↳ logs"]
    lines.append(f"    count: {len(logs)}")
    for index, event in enumerate(logs[-5:], start=1):
        lines.extend(_render_log_event_block(index=index, event=event))
    return _join_output_block(lines)


def _render_body_result(*, result: ActionResult) -> str:
    if result.run is not None and result.run.error:
        return _join_output_block(_build_error_block(run=result.run))

    lines = [f"body_ref: {result.body_ref or '-'}"]
    if result.payload is not None:
        lines.append(_render_pretty_json(result.payload))
    return "".join(f"{line}\n" for line in lines)


def _render_global_runs(*, result: ActionResult) -> str:
    runs = result.runs or []
    if not runs:
        return "runs: []\n"
    statuses = [status.strip().upper() for status in result.statuses or [] if status.strip()]
    header = "runs"
    if statuses == ["WAITING"]:
        header = "runs [waiting]"
    lines = [f"{header}\n"]
    for item in runs:
        run_id = str(item.get("id", "-"))
        status = str(item.get("status", "UNKNOWN"))
        skill_ref = _display_skill_ref(str(item.get("skill_ref", "<external>")))
        current = str(item.get("current", "-") or "-")
        status_icon = _build_run_status_icon(status)
        wait_suffix = _build_runs_wait_suffix(item)
        if statuses == ["WAITING"]:
            lines.append(f"  {status_icon} {run_id}  {skill_ref}  {current}  {wait_suffix}\n")
            continue
        if wait_suffix:
            lines.append(f"  {status_icon} {run_id}  {skill_ref}  {current}  {wait_suffix}\n")
            continue
        lines.append(f"  {status_icon} {run_id}  {skill_ref}  {current}\n")
    return "".join(lines)


def _render_server_result(*, result: ActionResult) -> str:
    payload = result.payload or {}
    if not payload:
        return "server\n  × url: -\n"
    running = bool(payload.get("running", False))
    endpoint = str(payload.get("endpoint", "")).strip() or "-"
    pid = payload.get("pid")
    managed = bool(payload.get("managed", False))

    lines = [
        "server",
        f"  {theme.icon_success if running else theme.icon_error} url: {endpoint}",
    ]
    if pid is not None:
        lines.append(f"    pid: {pid}")
    if managed:
        lines.append("    managed by skiller")
    return "".join(f"{line}\n" for line in lines)


def _render_webhooks(*, result: ActionResult) -> str:
    webhooks = result.webhooks or []
    if not webhooks:
        return "webhooks\n  (none)\n"
    lines = ["webhooks\n"]
    for item in webhooks:
        webhook = str(item.get("webhook", "-"))
        enabled = bool(item.get("enabled", False))
        created_at = str(item.get("created_at", "-"))
        icon = theme.icon_success if enabled else theme.icon_error
        lines.append(f"  {icon} {webhook:<12} {created_at}\n")
    return "".join(lines)


def _display_run_id(run: UiRun) -> str:
    if run.run_id is None:
        return "-"
    return run.run_id


def _build_runs_wait_suffix(item: dict[str, object]) -> str:
    wait_type = str(item.get("wait_type", "")).strip().lower()
    wait_detail = str(item.get("wait_detail", "")).strip()
    if not wait_type:
        return ""
    if not wait_detail:
        return wait_type
    return f"{wait_type}:[{_truncate_wait_detail(wait_detail)}]"


def _display_skill_ref(skill_ref: str) -> str:
    normalized = skill_ref.strip()
    if not normalized:
        return "<external>"
    if "/" not in normalized and "\\" not in normalized:
        return normalized
    return Path(normalized).name or normalized


def _build_run_status_icon(status: str) -> str:
    normalized = status.strip().upper()
    if normalized == "SUCCEEDED":
        return theme.icon_success
    if normalized == "FAILED":
        return theme.icon_error
    if normalized == "WAITING":
        return theme.icon_waiting
    if normalized == "RUNNING":
        return theme.icon_running
    if normalized == "CREATED":
        return theme.icon_created
    return "?"


def _truncate_wait_detail(detail: str, *, max_chars: int = 24) -> str:
    normalized = detail.strip()
    if len(normalized) <= max_chars:
        return normalized
    return normalized[: max_chars - 3].rstrip() + "..."


def _render_log_event_block(*, index: int, event: dict[str, object]) -> list[str]:
    lines = [f"    [{index}]"]
    rendered_event = _render_pretty_json(event)
    lines.extend(f"      {line}" for line in rendered_event.splitlines())
    return lines


def _render_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True)


def _render_pretty_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2)


def _build_watch_blocks_from_events(
    *,
    run: UiRun,
    events: list[object],
    block_kind: str | None = None,
) -> list[str]:
    normalized_events = _trim_stale_leading_waiting_events(events)
    header_kind = block_kind or _infer_execution_block_kind(events)
    header = _build_execution_block_header(run, kind=header_kind)
    lines: list[str] = [header]
    rendered_error_messages: set[str] = set()

    for item in normalized_events:
        if not isinstance(item, dict):
            continue

        event_name = str(item.get("type", "")).strip().upper()
        payload = item.get("payload", {})
        if not isinstance(payload, dict):
            payload = {}

        if event_name == "STEP_SUCCESS":
            step_id = str(payload.get("step", "")).strip()
            step_type = str(payload.get("step_type", "")).strip() or "step"
            if step_type in {"wait_input", "wait_webhook"}:
                continue
            result_detail = _extract_step_result_detail(
                step_type=step_type,
                result=payload.get("output"),
            )
            lines.extend(
                _build_watch_step_block(
                    step_id=step_id,
                    step_type=step_type,
                    detail=result_detail,
                )
            )
            continue

        if event_name == "RUN_WAITING":
            step_id = str(payload.get("step", "")).strip()
            step_type = str(payload.get("step_type", "")).strip() or "wait"
            result_detail = _extract_step_result_detail(
                step_type=step_type,
                result=payload.get("output"),
            )
            lines.extend(
                _build_watch_step_block(
                    step_id=step_id,
                    step_type=step_type,
                    detail=result_detail,
                )
            )
            continue

        if event_name == "STEP_ERROR":
            message = str(payload.get("error", "")).strip()
            if message and message in rendered_error_messages:
                continue
            error_lines = _build_error_block(run=run, header=header)
            if message:
                error_lines[-1] = f"    {message}"
                rendered_error_messages.add(message)
            lines.extend(error_lines[1:])
            continue

        is_run_finished_error = (
            event_name == "RUN_FINISHED"
            and str(payload.get("status", "")).upper() == "FAILED"
        )
        if is_run_finished_error:
            message = str(payload.get("error", "")).strip()
            if message and message in rendered_error_messages:
                continue
            error_lines = _build_error_block(run=run, header=header)
            if message:
                error_lines[-1] = f"    {message}"
                rendered_error_messages.add(message)
            lines.extend(error_lines[1:])

    return lines


def _infer_execution_block_kind(events: list[object]) -> str:
    has_run_create = False
    has_run_resume = False
    has_run_waiting = False
    has_completed_step = False
    for item in events:
        if not isinstance(item, dict):
            continue
        event_name = str(item.get("type", "")).strip().upper()
        if event_name == "RUN_RESUME":
            has_run_resume = True
            continue
        if event_name == "RUN_WAITING":
            has_run_waiting = True
            continue
        if event_name in {"STEP_SUCCESS", "STEP_ERROR", "RUN_FINISHED"}:
            has_completed_step = True
            continue
        if event_name == "RUN_CREATE":
            has_run_create = True
            continue
    if has_run_resume or has_completed_step:
        return "run-resume"
    if has_run_waiting:
        return "run-wait"
    if has_run_create:
        return "run-create"
    return "run-resume"


def _trim_stale_leading_waiting_events(events: list[object]) -> list[object]:
    displayable_kinds: list[tuple[int, str]] = []
    for index, item in enumerate(events):
        if not isinstance(item, dict):
            continue
        event_name = str(item.get("type", "")).strip().upper()
        payload = item.get("payload", {})
        if not isinstance(payload, dict):
            payload = {}

        if event_name == "RUN_WAITING":
            displayable_kinds.append((index, "waiting"))
            continue

        if event_name == "STEP_SUCCESS":
            step_type = str(payload.get("step_type", "")).strip().lower()
            if step_type in {"wait_input", "wait_webhook"}:
                continue
            displayable_kinds.append((index, "step"))
            continue

        if event_name in {"STEP_ERROR", "RUN_FINISHED"}:
            displayable_kinds.append((index, "terminal"))

    if not displayable_kinds:
        return list(events)

    first_non_waiting_index: int | None = None
    for index, kind in displayable_kinds:
        if kind != "waiting":
            first_non_waiting_index = index
            break

    if first_non_waiting_index is None:
        return list(events)

    return list(events[first_non_waiting_index:])


def _normalize_output_text(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        return ""

    if normalized.startswith('"') and normalized.endswith('"'):
        try:
            parsed = json.loads(normalized)
        except json.JSONDecodeError:
            pass
        else:
            if isinstance(parsed, str):
                normalized = parsed

    if "\\u" not in normalized and "\\n" not in normalized and '\\"' not in normalized:
        return normalized

    try:
        decoded = codecs_decode(normalized, "unicode_escape")
    except UnicodeDecodeError:
        return normalized
    return decoded.strip()


def _extract_step_result_detail(*, step_type: str, result: object) -> str:
    if result is None:
        return ""
    if not isinstance(result, dict):
        return _normalize_output_text(_render_json(result))

    text = str(result.get("text", "")).strip()
    if text:
        return _normalize_output_text(text)

    value = result.get("value")
    if value is None:
        return ""
    return _normalize_output_text(_render_json(value))


def _render_waiting_hints(*, run: UiRun) -> list[str]:
    if run.run_id is None:
        return []
    lines: list[str] = []
    waiting_metadata = _get_waiting_metadata(run.last_payload)
    if waiting_metadata is not None and waiting_metadata["wait_type"] == "input":
        lines.append(f"reply: /input {run.run_id} <text>")
    lines.append(f"watch: /watch {run.run_id}")
    return lines


def _render_waiting_metadata(*, metadata: dict[str, str]) -> list[str]:
    if metadata["wait_type"] == "webhook":
        return [f"webhook: {metadata['webhook']}", f"key: {metadata['key']}"]
    if metadata["wait_type"] == "input":
        return [f"prompt: {metadata['prompt']}"]
    return []


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


def _join_output_block(lines: list[str]) -> str:
    return "".join(f"{line}\n" for line in lines)


def _wrap_detail_lines(*, detail: str, indent: str = "    ") -> list[str]:
    normalized = detail.strip()
    if not normalized:
        return []

    wrapper = textwrap.TextWrapper(
        width=_DETAIL_WRAP_WIDTH,
        initial_indent=indent,
        subsequent_indent=indent,
        break_long_words=False,
        break_on_hyphens=False,
    )

    wrapped_lines: list[str] = []
    for paragraph in normalized.splitlines():
        stripped = paragraph.strip()
        if not stripped:
            wrapped_lines.append(indent.rstrip())
            continue
        wrapped_lines.extend(wrapper.fill(stripped).splitlines())
    return wrapped_lines


def _build_waiting_block(
    *,
    run: UiRun,
    metadata: dict[str, str],
    header: str | None = None,
) -> list[str]:
    wait_type = metadata["wait_type"]
    lines = [header or _build_run_block_header(run), f"  ↳ waiting {wait_type}"]
    if wait_type == "input":
        lines.extend(_wrap_detail_lines(detail=metadata["prompt"]))
    elif wait_type == "webhook":
        lines.extend(_wrap_detail_lines(detail=metadata["webhook"]))
        lines.extend(_wrap_detail_lines(detail=f"key: {metadata['key']}"))
    return lines


def _build_watch_step_block(*, step_id: str, step_type: str, detail: str = "") -> list[str]:
    header_step_id = step_id or "step"
    lines = [f"  [{step_type}] {header_step_id}"]
    normalized_detail = detail.strip()
    if normalized_detail:
        lines.extend(_wrap_detail_lines(detail=normalized_detail))
    return lines


def _build_success_block(*, run: UiRun, header: str | None = None) -> list[str]:
    return [header or _build_run_block_header(run), "  ↳ success"]


def _build_error_block(*, run: UiRun, header: str | None = None) -> list[str]:
    lines = [header or _build_run_block_header(run), "  ↳ error"]
    lines.extend(_wrap_detail_lines(detail=_build_run_error_message(run)))
    return lines


def _build_run_summary_block(*, run: UiRun, label: str, header: str | None = None) -> list[str]:
    return [header or _build_run_block_header(run), f"  ↳ {label.lower()}"]


def _build_run_create_block(*, run: UiRun, metadata: dict[str, str]) -> list[str]:
    header = _build_execution_block_header(run, kind="run-create")
    step_id = str(run.last_payload.get("current", "")).strip() or "step"
    wait_type = metadata["wait_type"]
    lines = [header, f"  [wait_{wait_type}] {step_id}"]
    if wait_type == "input":
        lines.extend(_wrap_detail_lines(detail=metadata["prompt"]))
    elif wait_type == "webhook":
        webhook = metadata["webhook"]
        key = metadata["key"]
        lines.extend(_wrap_detail_lines(detail=f"{webhook}:{key}"))
    return lines


def _build_execution_block_header(run: UiRun, *, kind: str) -> str:
    label = run.raw_args or "<empty>"
    short_run_id = _display_run_id_short(run) or "-"
    return f"[{kind}] {label}:{short_run_id}"


def _build_run_block_header(run: UiRun) -> str:
    short_run_id = _display_run_id_short(run)
    if short_run_id is None:
        return f"run: {run.raw_args or '<empty>'}"
    return f"run-{short_run_id}: {run.raw_args or '<empty>'}"


def _display_run_id_short(run: UiRun) -> str | None:
    run_id = run.run_id
    if run_id is None:
        return None
    normalized = run_id.strip()
    if not normalized:
        return None
    return normalized[-4:]
