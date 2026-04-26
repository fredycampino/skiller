import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

from skiller.di.container import build_runtime_container
from skiller.domain.run.run_model import RunStatus, SkillSource
from skiller.interfaces.runtime_controller import RuntimeController
from skiller.local.channels.whatsapp.pair_service import WhatsAppPairService
from skiller.local.channels.whatsapp.process_service import WhatsAppProcessService
from skiller.local.server.process_service import WebhookProcessService
from skiller.local.tunnels.cloudflared.ensure_service import CloudflaredEnsureService
from skiller.local.tunnels.cloudflared.login_service import CloudflaredLoginService
from skiller.local.tunnels.cloudflared.process_service import CloudflaredProcessService
from skiller.local.workers.process_service import WorkerProcessService

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


def _normalize_status_filters(statuses: list[str] | None) -> list[str]:
    normalized: list[str] = []
    for status in statuses or []:
        value = status.strip().upper()
        if not value:
            continue
        normalized.append(value)
    return normalized


def _merge_waiting_metadata(
    run_result: dict[str, Any],
    status_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    if status_payload is None:
        return run_result

    for field in ("current", "wait_type", "webhook", "key", "prompt", "channel"):
        if field in status_payload:
            run_result[field] = status_payload[field]
    return run_result


def _resolve_run_target(
    parser: argparse.ArgumentParser,
    args: argparse.Namespace,
) -> tuple[str, str]:
    if bool(args.skill) == bool(args.skill_file):
        parser.error("Use either an internal skill name or --file PATH.")

    if args.skill_file:
        return args.skill_file, SkillSource.FILE.value

    return args.skill, SkillSource.INTERNAL.value


def _maybe_start_server(
    args: argparse.Namespace,
    controller: RuntimeController,
    container_settings: Any,
    run_result: dict[str, Any],
) -> tuple[dict[str, Any], int]:
    if not args.start_server:
        return run_result, 0

    try:
        server_result = WebhookProcessService(container_settings).start()
        run_result["server_started"] = server_result.started
        run_result["server_endpoint"] = server_result.endpoint
        if server_result.pid is not None:
            run_result["server_pid"] = server_result.pid
        return run_result, 0
    except RuntimeError as exc:
        run_result["server_started"] = False
        run_result["error"] = str(exc)
        if args.logs:
            run_result["logs"] = controller.logs(run_result["run_id"])
        return run_result, 1


def _watch_run(
    controller: RuntimeController,
    run_id: str,
    *,
    initial_status: str = RunStatus.CREATED.value,
) -> dict[str, Any]:
    last_status = ""
    seen_event_ids: set[str] = set()
    collected_events: list[dict[str, Any]] = []

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
            collected_events.append(dict(event))
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
                "events": collected_events,
            }

        time.sleep(0.1)


def _print_watch_status(run_id: str, status: str) -> None:
    print(f"[{_display_run_id(run_id)}] {status}", file=sys.stderr, flush=True)


def _format_watch_event(run_id: str, event: dict[str, Any]) -> str | None:
    event_type = str(event.get("type", "")).strip().upper()
    if not event_type:
        return None

    payload = event.get("payload", {})
    if not isinstance(payload, dict):
        return f"[{_display_run_id(run_id)}] {event_type}"

    label = event_type
    parts: list[str] = []

    if event_type == "RUN_CREATE":
        parts = [
            _format_field("skill", payload.get("skill")),
            _format_field("skill_source", payload.get("skill_source")),
        ]
    elif event_type == "RUN_RESUME":
        parts = [_format_field("source", payload.get("source"))]
    elif event_type == "STEP_STARTED":
        parts = [
            _format_field("step", payload.get("step")),
            _format_field("step_type", payload.get("step_type")),
        ]
    elif event_type == "STEP_SUCCESS":
        parts = [
            _format_field("step", payload.get("step")),
            _format_field("step_type", payload.get("step_type")),
            _format_field("output", payload.get("output")),
            _format_field("next", payload.get("next")),
        ]
    elif event_type == "STEP_ERROR":
        parts = [
            _format_field("step", payload.get("step")),
            _format_field("step_type", payload.get("step_type")),
            _format_field("error", payload.get("error")),
        ]
    elif event_type == "RUN_WAITING":
        parts = [
            _format_field("step", payload.get("step")),
            _format_field("step_type", payload.get("step_type")),
            _format_field("output", payload.get("output")),
        ]
    elif event_type == "RUN_FINISHED":
        status = str(payload.get("status", "")).upper()
        if status == RunStatus.SUCCEEDED.value:
            return None
        parts = [
            _format_field("status", payload.get("status")),
            _format_field("error", payload.get("error")),
        ]
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
        raw = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    if len(raw) <= 120:
        return raw
    return f"{raw[:117]}..."


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="skiller", description="Skiller Runtime CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("ui", help="Open the interactive TUI")
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
        "--start-server",
        action="store_true",
        help="Start the local webhooks server before dispatching the run",
    )
    run_parser.add_argument(
        "--detach",
        action="store_true",
        help="Return after dispatching the worker without waiting for terminal status",
    )

    resume_parser = sub.add_parser("resume", help="Resume a waiting run")
    resume_parser.add_argument("run_id")

    delete_parser = sub.add_parser("delete", help="Delete a run and all associated database rows")
    delete_parser.add_argument("run_id")

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

    runs_parser = sub.add_parser("runs", help="List recent runs")
    runs_parser.add_argument("--limit", type=int, default=20)
    runs_parser.add_argument("--status", action="append", default=[])

    logs_parser = sub.add_parser("logs", help="List run events")
    logs_parser.add_argument("run_id")

    execution_output_parser = sub.add_parser(
        "execution-output",
        help="Get persisted output body by body_ref",
    )
    execution_output_parser.add_argument("body_ref")

    watch_parser = sub.add_parser("watch", help="Watch a run until it finishes or waits")
    watch_parser.add_argument("run_id")

    input_parser = sub.add_parser("input", help="Human input operations")
    input_sub = input_parser.add_subparsers(dest="input_command", required=True)

    input_receive_parser = input_sub.add_parser(
        "receive",
        help="Receive human input into a waiting run",
    )
    input_receive_parser.add_argument("run_id", help="Run id")
    input_receive_parser.add_argument("--text", required=True, help="Input text")

    channel_parser = sub.add_parser("channel", help="Channel ingress operations")
    channel_sub = channel_parser.add_subparsers(dest="channel_command", required=True)

    channel_receive_parser = channel_sub.add_parser(
        "receive",
        help="Receive a channel message into the runtime",
    )
    channel_receive_parser.add_argument("channel", help="Channel name (e.g. whatsapp)")
    channel_receive_parser.add_argument("key", help="Channel correlation key")
    channel_receive_parser.add_argument("--json", dest="json_inline", help="JSON payload string")
    channel_receive_parser.add_argument("--json-file", help="Path to JSON payload file")
    channel_receive_parser.add_argument("--external-id", help="External message id")
    channel_receive_parser.add_argument(
        "--dedup-key",
        help="Stable deduplication key for idempotent channel delivery",
    )

    webhook_parser = sub.add_parser("webhook", help="Webhook operations")
    webhook_sub = webhook_parser.add_subparsers(dest="webhook_command", required=True)

    server_parser = sub.add_parser("server", help="Server operations")
    server_sub = server_parser.add_subparsers(dest="server_command", required=True)
    server_sub.add_parser("start", help="Start the local webhooks server")
    server_sub.add_parser("status", help="Show local webhooks server status")
    server_sub.add_parser("stop", help="Stop the local webhooks server")

    cloudflared_parser = sub.add_parser("cloudflared", help="Cloudflared tunnel operations")
    cloudflared_sub = cloudflared_parser.add_subparsers(
        dest="cloudflared_command",
        required=True,
    )
    cloudflared_sub.add_parser("start", help="Start the local cloudflared connector")
    cloudflared_sub.add_parser("status", help="Show local cloudflared connector status")
    cloudflared_sub.add_parser("stop", help="Stop the local cloudflared connector")
    cloudflared_ensure_parser = cloudflared_sub.add_parser(
        "ensure",
        help="Ensure the remote cloudflared tunnel and DNS route exist",
    )
    cloudflared_ensure_parser.add_argument("--domain", required=True, help="Base domain")
    cloudflared_login_parser = cloudflared_sub.add_parser(
        "login",
        help="Cloudflared login operations",
    )
    cloudflared_login_sub = cloudflared_login_parser.add_subparsers(
        dest="cloudflared_login_command",
        required=True,
    )
    cloudflared_login_sub.add_parser("start", help="Start cloudflared tunnel login")
    cloudflared_login_sub.add_parser("status", help="Show cloudflared login status")
    cloudflared_login_sub.add_parser("stop", help="Stop a managed cloudflared login attempt")

    whatsapp_parser = sub.add_parser("whatsapp", help="WhatsApp operations")
    whatsapp_sub = whatsapp_parser.add_subparsers(dest="whatsapp_command", required=True)
    whatsapp_sub.add_parser("start", help="Start the local WhatsApp bridge")
    whatsapp_sub.add_parser("status", help="Show local WhatsApp bridge status")
    whatsapp_sub.add_parser("stop", help="Stop the local WhatsApp bridge")
    whatsapp_pair_parser = whatsapp_sub.add_parser("pair", help="WhatsApp pairing operations")
    whatsapp_pair_sub = whatsapp_pair_parser.add_subparsers(
        dest="whatsapp_pair_command",
        required=True,
    )
    whatsapp_pair_sub.add_parser("start", help="Start WhatsApp pairing")
    whatsapp_pair_sub.add_parser("status", help="Show WhatsApp pairing status")
    whatsapp_pair_sub.add_parser("stop", help="Stop a managed WhatsApp pairing attempt")
    whatsapp_pair_sub.add_parser("reset", help="Delete local WhatsApp session and pairing state")

    register_parser = webhook_sub.add_parser(
        "register",
        help="Register a webhook channel and generate its secret",
    )
    register_parser.add_argument("webhook", help="Webhook channel name")

    webhook_sub.add_parser("list", help="List registered webhook channels")

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
    effective_argv = list(sys.argv[1:] if argv is None else argv)
    if not effective_argv:
        from skiller.interfaces.tui.app import run_tui

        run_tui()
        return 0

    parser = build_parser()
    args = parser.parse_args(effective_argv)
    if args.command == "ui":
        from skiller.interfaces.ui.app import run_ui

        run_ui()
        return 0

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

        run_result, exit_code = _maybe_start_server(
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
            if not args.detach:
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
                if watched["status"] == RunStatus.WAITING.value:
                    run_result = _merge_waiting_metadata(
                        run_result,
                        controller.status(run_result["run_id"]),
                    )
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

    if args.command == "server" and args.server_command == "start":
        try:
            result = WebhookProcessService(container.settings).start()
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(
            json.dumps(
                {
                    "started": result.started,
                    "running": result.running,
                    "managed_by_skiller": result.managed,
                    "endpoint": result.endpoint,
                    "pid": result.pid,
                },
                indent=2,
            )
        )
        return 0

    if args.command == "server" and args.server_command == "status":
        result = WebhookProcessService(container.settings).status()
        print(
            json.dumps(
                {
                    "running": result.running,
                    "managed_by_skiller": result.managed,
                    "endpoint": result.endpoint,
                    "pid": result.pid,
                },
                indent=2,
            )
        )
        return 0

    if args.command == "server" and args.server_command == "stop":
        try:
            result = WebhookProcessService(container.settings).stop()
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(
            json.dumps(
                {
                    "stopped": result.stopped,
                    "running": result.running,
                    "managed_by_skiller": result.managed,
                    "endpoint": result.endpoint,
                    "pid": result.pid,
                },
                indent=2,
            )
        )
        return 0 if result.stopped or not result.running else 1

    if args.command == "cloudflared" and args.cloudflared_command == "start":
        try:
            result = CloudflaredProcessService(container.settings).start()
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(
            json.dumps(
                {
                    "started": result.started,
                    "running": result.running,
                    "managed_by_skiller": result.managed,
                    "origin_url": result.origin_url,
                    "tunnel_name": result.tunnel_name,
                    "pid": result.pid,
                },
                indent=2,
            )
        )
        return 0

    if args.command == "cloudflared" and args.cloudflared_command == "status":
        result = CloudflaredProcessService(container.settings).status()
        print(
            json.dumps(
                {
                    "running": result.running,
                    "managed_by_skiller": result.managed,
                    "origin_url": result.origin_url,
                    "tunnel_name": result.tunnel_name,
                    "pid": result.pid,
                },
                indent=2,
            )
        )
        return 0

    if args.command == "cloudflared" and args.cloudflared_command == "stop":
        try:
            result = CloudflaredProcessService(container.settings).stop()
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(
            json.dumps(
                {
                    "stopped": result.stopped,
                    "running": result.running,
                    "managed_by_skiller": result.managed,
                    "origin_url": result.origin_url,
                    "tunnel_name": result.tunnel_name,
                    "pid": result.pid,
                },
                indent=2,
            )
        )
        return 0 if result.stopped or not result.managed else 1

    if args.command == "cloudflared" and args.cloudflared_command == "ensure":
        try:
            result = CloudflaredEnsureService(container.settings).ensure(domain=args.domain)
        except (RuntimeError, ValueError) as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(
            json.dumps(
                {
                    "authenticated": result.authenticated,
                    "tunnel_name": result.tunnel_name,
                    "tunnel_id": result.tunnel_id,
                    "hostname": result.hostname,
                    "created": result.created,
                    "dns_status": result.dns_status,
                    "config_path": result.config_path,
                    "home": result.home,
                },
                indent=2,
            )
        )
        return 0

    if args.command == "cloudflared" and args.cloudflared_command == "login":
        if args.cloudflared_login_command == "start":
            try:
                result = CloudflaredLoginService(container.settings).start()
            except RuntimeError as exc:
                print(str(exc), file=sys.stderr)
                return 1
            print(
                json.dumps(
                    {
                        "authenticated": result.authenticated,
                        "started": result.started,
                        "running": result.running,
                        "pid": result.pid,
                        "home": result.home,
                        "cert_path": result.cert_path,
                        "log_path": result.log_path,
                    },
                    indent=2,
                )
            )
            return 0

        if args.cloudflared_login_command == "status":
            result = CloudflaredLoginService(container.settings).status()
            print(
                json.dumps(
                    {
                        "authenticated": result.authenticated,
                        "running": result.running,
                        "pid": result.pid,
                        "home": result.home,
                        "cert_path": result.cert_path,
                        "log_path": result.log_path,
                    },
                    indent=2,
                )
            )
            return 0

        if args.cloudflared_login_command == "stop":
            try:
                result = CloudflaredLoginService(container.settings).stop()
            except RuntimeError as exc:
                print(str(exc), file=sys.stderr)
                return 1
            print(
                json.dumps(
                    {
                        "authenticated": result.authenticated,
                        "stopped": result.stopped,
                        "running": result.running,
                        "pid": result.pid,
                        "home": result.home,
                        "cert_path": result.cert_path,
                        "log_path": result.log_path,
                    },
                    indent=2,
                )
            )
            return 0 if result.stopped or not result.running else 1

    if args.command == "whatsapp" and args.whatsapp_command == "start":
        try:
            result = WhatsAppProcessService(container.settings).start()
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(
            json.dumps(
                {
                    "started": result.started,
                    "running": result.running,
                    "managed_by_skiller": result.managed,
                    "paired": result.paired,
                    "state": result.state,
                    "qr_count": result.qr_count,
                    "queue_length": result.queue_length,
                    "endpoint": result.endpoint,
                    "session_path": result.session_path,
                    "pid": result.pid,
                },
                indent=2,
            )
        )
        return 0

    if args.command == "whatsapp" and args.whatsapp_command == "status":
        result = WhatsAppProcessService(container.settings).status()
        print(
            json.dumps(
                {
                    "running": result.running,
                    "managed_by_skiller": result.managed,
                    "paired": result.paired,
                    "state": result.state,
                    "qr_count": result.qr_count,
                    "queue_length": result.queue_length,
                    "endpoint": result.endpoint,
                    "session_path": result.session_path,
                    "pid": result.pid,
                },
                indent=2,
            )
        )
        return 0

    if args.command == "whatsapp" and args.whatsapp_command == "stop":
        try:
            result = WhatsAppProcessService(container.settings).stop()
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(
            json.dumps(
                {
                    "stopped": result.stopped,
                    "running": result.running,
                    "managed_by_skiller": result.managed,
                    "paired": result.paired,
                    "state": result.state,
                    "qr_count": result.qr_count,
                    "queue_length": result.queue_length,
                    "endpoint": result.endpoint,
                    "session_path": result.session_path,
                    "pid": result.pid,
                },
                indent=2,
            )
        )
        return 0 if result.stopped or not result.running else 1

    if args.command == "whatsapp" and args.whatsapp_command == "pair":
        if args.whatsapp_pair_command == "start":
            try:
                result = WhatsAppPairService(container.settings).start()
            except RuntimeError as exc:
                print(str(exc), file=sys.stderr)
                return 1
            print(
                json.dumps(
                    {
                        "paired": result.paired,
                        "started": result.started,
                        "running": result.running,
                        "pid": result.pid,
                        "state": result.state,
                        "qr_count": result.qr_count,
                        "home": result.home,
                        "session_path": result.session_path,
                        "log_path": result.log_path,
                    },
                    indent=2,
                )
            )
            return 0

        if args.whatsapp_pair_command == "status":
            result = WhatsAppPairService(container.settings).status()
            print(
                json.dumps(
                    {
                        "paired": result.paired,
                        "running": result.running,
                        "pid": result.pid,
                        "state": result.state,
                        "qr_count": result.qr_count,
                        "home": result.home,
                        "session_path": result.session_path,
                        "log_path": result.log_path,
                    },
                    indent=2,
                )
            )
            return 0

        if args.whatsapp_pair_command == "stop":
            try:
                result = WhatsAppPairService(container.settings).stop()
            except RuntimeError as exc:
                print(str(exc), file=sys.stderr)
                return 1
            print(
                json.dumps(
                    {
                        "paired": result.paired,
                        "stopped": result.stopped,
                        "running": result.running,
                        "pid": result.pid,
                        "state": result.state,
                        "qr_count": result.qr_count,
                        "home": result.home,
                        "session_path": result.session_path,
                        "log_path": result.log_path,
                    },
                    indent=2,
                )
            )
            return 0 if result.stopped or not result.running else 1

        if args.whatsapp_pair_command == "reset":
            try:
                stop_result = WhatsAppProcessService(container.settings).stop()
                result = WhatsAppPairService(container.settings).reset()
            except RuntimeError as exc:
                print(str(exc), file=sys.stderr)
                return 1
            print(
                json.dumps(
                    {
                        "reset": result.reset,
                        "paired": result.paired,
                        "stopped_bridge": stop_result.stopped,
                        "stopped_pairing": result.stopped_pairing,
                        "home": result.home,
                        "session_path": result.session_path,
                    },
                    indent=2,
                )
            )
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

    if args.command == "delete":
        result = controller.delete_run(args.run_id)
        print(json.dumps(result, indent=2))
        return 0 if result["deleted"] else 1

    if args.command == "status":
        run = controller.status(args.run_id)
        if run is None:
            print("Run not found")
            return 1
        print(json.dumps(run, indent=2))
        return 0

    if args.command == "runs":
        runs = controller.list_runs(
            limit=args.limit,
            statuses=_normalize_status_filters(args.status),
        )
        print(json.dumps(runs, indent=2))
        return 0

    if args.command == "logs":
        events = controller.logs(args.run_id)
        print(json.dumps(events, indent=2))
        return 0

    if args.command == "execution-output":
        try:
            output_body = controller.get_execution_output(args.body_ref)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        if output_body is None:
            print("Execution output not found", file=sys.stderr)
            return 1
        print(json.dumps(output_body, indent=2))
        return 0

    if args.command == "watch":
        try:
            result = _watch_run(controller, args.run_id, initial_status="")
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(json.dumps(result, indent=2))
        return 0 if result["status"] != RunStatus.FAILED.value else 1

    if args.command == "input" and args.input_command == "receive":
        result = controller.receive_input(args.run_id, text=args.text)
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
        return 0 if result["accepted"] else 1

    if args.command == "channel" and args.channel_command == "receive":
        payload = _load_json_payload(args.json_inline, args.json_file)
        result = controller.receive_channel(
            args.channel,
            args.key,
            payload,
            external_id=args.external_id,
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
        return 0 if result["accepted"] else 1

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

    if args.command == "webhook" and args.webhook_command == "list":
        result = controller.list_webhooks()
        print(json.dumps(result, indent=2))
        return 0

    if args.command == "webhook" and args.webhook_command == "remove":
        result = controller.remove_webhook(args.webhook)
        print(json.dumps(result, indent=2))
        return 0 if result["removed"] else 1

    parser.print_help()
    return 1
