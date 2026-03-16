import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

from skiller.di.container import build_runtime_container
from skiller.domain.run_model import RunStatus, SkillSource
from skiller.interfaces.controllers import RuntimeController
from skiller.tools.webhooks.process_service import WebhookProcessService
from skiller.tools.workers.process_service import WorkerProcessService

_WATCH_TERMINAL_STATUSES = {
    RunStatus.WAITING.value,
    RunStatus.SUCCEEDED.value,
    RunStatus.FAILED.value,
    RunStatus.CANCELLED.value,
}


def _parse_key_value(pairs: list[str]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for pair in pairs:
        if "=" not in pair:
            raise ValueError(f"Invalid --arg '{pair}'. Expected key=value.")
        key, value = pair.split("=", 1)
        parsed[key] = value
    return parsed


def _load_json_payload(inline_json: str | None, json_file: str | None) -> dict:
    if inline_json and json_file:
        raise ValueError("Use either --json or --json-file, not both.")
    if inline_json:
        payload = json.loads(inline_json)
    elif json_file:
        payload = json.loads(Path(json_file).read_text(encoding="utf-8"))
    else:
        payload = {}

    if not isinstance(payload, dict):
        raise ValueError("Webhook payload must be a JSON object.")
    return payload


def _resolve_run_target(
    parser: argparse.ArgumentParser,
    args: argparse.Namespace,
) -> tuple[str, str]:
    if bool(args.skill) == bool(args.skill_file):
        parser.error("Use either an internal skill name or --file PATH.")

    if args.skill_file:
        return args.skill_file, SkillSource.FILE.value

    return args.skill, SkillSource.INTERNAL.value


def _maybe_start_webhooks(
    args: argparse.Namespace,
    controller: RuntimeController,
    container_settings: Any,
    run_result: dict[str, Any],
) -> tuple[dict[str, Any], int]:
    if not args.start_webhooks:
        return run_result, 0

    try:
        webhooks_result = WebhookProcessService(container_settings).start()
        run_result["webhooks_started"] = webhooks_result.started
        run_result["webhooks_endpoint"] = webhooks_result.endpoint
        if webhooks_result.pid is not None:
            run_result["webhooks_pid"] = webhooks_result.pid
        return run_result, 0
    except RuntimeError as exc:
        run_result["webhooks_started"] = False
        run_result["error"] = str(exc)
        if args.logs:
            run_result["logs"] = controller.logs(run_result["run_id"])
        return run_result, 1


def _watch_run(
    controller: RuntimeController,
    run_id: str,
    *,
    initial_status: str = RunStatus.CREATED.value,
) -> dict[str, str]:
    last_status = ""
    seen_event_ids: set[str] = set()

    if initial_status:
        _print_watch_status(run_id, initial_status)
        last_status = initial_status

    while True:
        run = controller.status(run_id)
        if run is None:
            raise RuntimeError(f"Run '{run_id}' not found during watch")

        events = controller.logs(run_id)
        for event in events:
            event_id = str(event.get("id", "")).strip()
            if not event_id or event_id in seen_event_ids:
                continue
            seen_event_ids.add(event_id)
            formatted_event = _format_watch_event(run_id, event)
            if formatted_event is None:
                continue
            print(formatted_event, file=sys.stderr, flush=True)

        status = str(run.get("status", "")).upper()
        if status and status != last_status:
            _print_watch_status(run_id, status)
            last_status = status

        if status in _WATCH_TERMINAL_STATUSES:
            return {
                "run_id": str(run.get("id", run_id)),
                "status": status,
            }

        time.sleep(0.1)


def _print_watch_status(run_id: str, status: str) -> None:
    print(f"[{_display_run_id(run_id)}] {status}", file=sys.stderr, flush=True)


def _format_watch_event(run_id: str, event: dict[str, Any]) -> str | None:
    event_type = str(event.get("type", "")).strip().upper()
    if not event_type or event_type == "RUN_FINISHED":
        return None

    payload = event.get("payload", {})
    if not isinstance(payload, dict):
        return f"[{_display_run_id(run_id)}] {event_type}"

    label = event_type
    parts: list[str] = []

    if event_type == "NOTIFY":
        parts = [
            _format_field("step", payload.get("step")),
            _format_field("message", payload.get("message")),
        ]
    elif event_type == "ASSIGN_RESULT":
        label = "ASSIGN"
        parts = [
            _format_field("step", payload.get("step")),
            _format_field("result", payload.get("result")),
        ]
    elif event_type == "LLM_PROMPT_RESULT":
        label = "LLM_PROMPT"
        parts = [
            _format_field("step", payload.get("step")),
            _format_field("model", payload.get("model")),
            _format_field("result", payload.get("result")),
        ]
    elif event_type == "LLM_PROMPT_ERROR":
        parts = [
            _format_field("step", payload.get("step")),
            _format_field("model", payload.get("model")),
            _format_field("error", payload.get("error")),
        ]
    elif event_type == "MCP_RESULT":
        label = "MCP"
        result = payload.get("result")
        parts = [
            _format_field("step", payload.get("step")),
            _format_field("mcp", payload.get("mcp")),
            _format_field("tool", payload.get("tool")),
        ]
        if isinstance(result, dict):
            if "ok" in result:
                parts.append(_format_field("ok", result.get("ok")))
            if result.get("ok") is False and "error" in result:
                parts.append(_format_field("error", result.get("error")))
    elif event_type == "SWITCH_DECISION":
        label = "SWITCH"
        parts = [
            _format_field("step", payload.get("step")),
            _format_field("value", payload.get("value")),
            _format_field("next", payload.get("next")),
        ]
    elif event_type == "WHEN_DECISION":
        label = "WHEN"
        parts = [
            _format_field("step", payload.get("step")),
            _format_field("op", payload.get("op")),
            _format_field("right", payload.get("right")),
            _format_field("next", payload.get("next")),
        ]
    elif event_type in {"WAITING", "WAIT_RESOLVED"}:
        parts = [
            _format_field("step", payload.get("step")),
            _format_field("webhook", payload.get("webhook")),
            _format_field("key", payload.get("key")),
        ]
    elif event_type == "RUN_RESUMED":
        parts = [_format_field("source", payload.get("source"))]
    elif event_type == "RUN_FAILED":
        parts = [_format_field("error", payload.get("error"))]
    else:
        parts = [_format_field(key, value) for key, value in payload.items()]

    rendered_parts = [part for part in parts if part]
    if not rendered_parts:
        return f"[{_display_run_id(run_id)}] {label}"
    return f"[{_display_run_id(run_id)}] {label} {' '.join(rendered_parts)}"


def _display_run_id(run_id: str) -> str:
    normalized = str(run_id).strip()
    if not normalized:
        return "-"

    tail = normalized.rsplit("-", 1)[-1]
    if len(tail) >= 4:
        return tail[-4:]
    if tail:
        return tail
    if len(normalized) <= 4:
        return normalized
    return normalized[-4:]


def _format_field(name: str, value: Any) -> str:
    if value is None:
        return ""
    return f"{name}={_compact_value(value)}"


def _compact_value(value: Any) -> str:
    if isinstance(value, str):
        raw = json.dumps(value, ensure_ascii=True)
    else:
        raw = json.dumps(value, ensure_ascii=True, sort_keys=True)
    if len(raw) <= 120:
        return raw
    return f"{raw[:117]}..."


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="skiller", description="Skiller Runtime CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init-db", help="Initialize SQLite schema")

    run_parser = sub.add_parser("run", help="Start a run with a skill")
    run_parser.add_argument("skill", nargs="?", help="Internal skill name (without extension)")
    run_parser.add_argument("--file", dest="skill_file", help="Path to an external skill file")
    run_parser.add_argument("--arg", action="append", default=[], help="Input pair key=value")
    run_parser.add_argument(
        "--logs",
        action="store_true",
        help="Include current run logs in the run response payload",
    )
    run_parser.add_argument(
        "--start-webhooks",
        action="store_true",
        help="Start the webhooks process before dispatching the run",
    )

    resume_parser = sub.add_parser("resume", help="Resume a waiting run")
    resume_parser.add_argument("run_id")

    worker_parser = sub.add_parser("worker", help="Worker operations")
    worker_sub = worker_parser.add_subparsers(dest="worker_command", required=True)

    worker_start_parser = worker_sub.add_parser(
        "start",
        help="Prepare a CREATED run and launch the worker",
    )
    worker_start_parser.add_argument("run_id")

    worker_run_parser = worker_sub.add_parser("run", help="Execute a prepared run")
    worker_run_parser.add_argument("run_id")

    worker_resume_parser = worker_sub.add_parser("resume", help="Resume a WAITING run")
    worker_resume_parser.add_argument("run_id")

    status_parser = sub.add_parser("status", help="Get run status")
    status_parser.add_argument("run_id")

    logs_parser = sub.add_parser("logs", help="List run events")
    logs_parser.add_argument("run_id")

    watch_parser = sub.add_parser("watch", help="Watch a run until it finishes or waits")
    watch_parser.add_argument("run_id")

    webhook_parser = sub.add_parser("webhook", help="Webhook operations")
    webhook_sub = webhook_parser.add_subparsers(dest="webhook_command", required=True)

    register_parser = webhook_sub.add_parser(
        "register",
        help="Register a webhook channel and generate its secret",
    )
    register_parser.add_argument("webhook", help="Webhook channel name")

    remove_parser = webhook_sub.add_parser("remove", help="Remove a webhook channel registration")
    remove_parser.add_argument("webhook", help="Webhook channel name")

    receive_parser = webhook_sub.add_parser(
        "receive",
        help="Receive a webhook payload into the runtime",
    )
    receive_parser.add_argument("webhook", help="Webhook channel (e.g. github-pr-merged)")
    receive_parser.add_argument("key", help="Webhook correlation key")
    receive_parser.add_argument("--json", dest="json_inline", help="JSON payload string")
    receive_parser.add_argument("--json-file", help="Path to JSON payload file")
    receive_parser.add_argument(
        "--dedup-key",
        help="Stable deduplication key for idempotent webhook delivery",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    container = build_runtime_container()
    controller = RuntimeController(
        runtime_service=container.runtime_service,
        query_service=container.query_service,
    )
    controller.initialize()

    if args.command == "init-db":
        print(f"DB initialized: {container.settings.db_path}")
        return 0

    if args.command == "run":
        try:
            skill_ref, skill_source = _resolve_run_target(parser, args)
            inputs = _parse_key_value(args.arg)
            run_result = controller.create_run(
                skill_ref,
                inputs,
                skill_source=skill_source,
            )
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1

        run_result, exit_code = _maybe_start_webhooks(
            args,
            controller,
            container.settings,
            run_result,
        )
        if exit_code == 0:
            try:
                worker_result = WorkerProcessService().start(run_result["run_id"])
                run_result["worker_pid"] = worker_result.pid
            except OSError as exc:
                print(str(exc), file=sys.stderr)
                return 1
            try:
                watched = _watch_run(
                    controller,
                    run_result["run_id"],
                    initial_status=run_result["status"],
                )
            except RuntimeError as exc:
                print(str(exc), file=sys.stderr)
                return 1
            run_result["status"] = watched["status"]
        if args.logs and "logs" not in run_result:
            run_result["logs"] = controller.logs(run_result["run_id"])
        print(json.dumps(run_result, indent=2))
        if exit_code != 0:
            return exit_code
        return 0 if run_result["status"] != RunStatus.FAILED.value else 1

    if args.command == "resume":
        try:
            worker_result = WorkerProcessService().resume(args.run_id)
        except OSError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        result = {
            "run_id": args.run_id,
            "resume_status": "DISPATCHED",
            "worker_pid": worker_result.pid,
        }
        print(json.dumps(result, indent=2))
        return 0

    if args.command == "worker" and args.worker_command == "start":
        try:
            result = controller.start_worker(args.run_id)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1

        if result["start_status"] == "PREPARED":
            try:
                worker_result = WorkerProcessService().run(args.run_id)
            except OSError as exc:
                print(str(exc), file=sys.stderr)
                return 1
            result["worker_pid"] = worker_result.pid
        print(json.dumps(result, indent=2))
        return 0 if result["start_status"] == "PREPARED" else 1

    if args.command == "worker" and args.worker_command == "run":
        try:
            result = controller.run_worker(args.run_id)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(json.dumps(result, indent=2))
        return 0 if result["status"] != "FAILED" else 1

    if args.command == "worker" and args.worker_command == "resume":
        result = controller.resume(args.run_id)
        print(json.dumps(result, indent=2))
        return 0 if result["resume_status"] == "RESUMED" else 1

    if args.command == "status":
        run = controller.status(args.run_id)
        if run is None:
            print("Run not found")
            return 1
        print(json.dumps(run, indent=2))
        return 0

    if args.command == "logs":
        events = controller.logs(args.run_id)
        print(json.dumps(events, indent=2))
        return 0

    if args.command == "watch":
        try:
            result = _watch_run(controller, args.run_id, initial_status="")
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(json.dumps(result, indent=2))
        return 0 if result["status"] != RunStatus.FAILED.value else 1

    if args.command == "webhook" and args.webhook_command == "receive":
        payload = _load_json_payload(args.json_inline, args.json_file)
        result = controller.receive_webhook(
            args.webhook,
            args.key,
            payload,
            dedup_key=args.dedup_key,
        )
        resumed_runs: list[str] = []
        for run_id in result["matched_runs"]:
            try:
                WorkerProcessService().resume(run_id)
            except OSError as exc:
                print(str(exc), file=sys.stderr)
                return 1
            resumed_runs.append(run_id)
        result["resumed_runs"] = resumed_runs
        print(json.dumps(result, indent=2))
        return 0

    if args.command == "webhook" and args.webhook_command == "register":
        result = controller.register_webhook(args.webhook)
        if result["status"] == "REGISTERED":
            result["webhook_url"] = (
                f"http://{container.settings.webhooks_host}:{container.settings.webhooks_port}"
                f"/webhooks/{result['webhook']}/{{key}}"
            )
        print(json.dumps(result, indent=2))
        return 0 if result["status"] == "REGISTERED" else 1

    if args.command == "webhook" and args.webhook_command == "remove":
        result = controller.remove_webhook(args.webhook)
        print(json.dumps(result, indent=2))
        return 0 if result["removed"] else 1

    parser.print_help()
    return 1
