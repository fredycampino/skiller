import argparse
import json
import sys
from pathlib import Path
from typing import Any

from skiller.di.container import build_runtime_container
from skiller.domain.run_model import SkillSource
from skiller.interfaces.controllers import RuntimeController
from skiller.tools.webhooks.process_service import WebhookProcessService


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
    if not args.start_webhooks or run_result["status"] != "WAITING":
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="skiller", description="Skiller Runtime CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init-db", help="Initialize SQLite schema")

    run_parser = sub.add_parser("run", help="Start a run with a skill")
    run_parser.add_argument("skill", nargs="?", help="Internal skill name (without extension)")
    run_parser.add_argument("--file", dest="skill_file", help="Path to an external skill file")
    run_parser.add_argument("--run-id", help="Explicit run id to assign before execution starts")
    run_parser.add_argument("--arg", action="append", default=[], help="Input pair key=value")
    run_parser.add_argument(
        "--logs",
        action="store_true",
        help="Include current run logs in the run response payload",
    )
    run_parser.add_argument(
        "--start-webhooks",
        action="store_true",
        help="Start the webhooks process if the run ends in WAITING",
    )

    resume_parser = sub.add_parser("resume", help="Resume a waiting run")
    resume_parser.add_argument("run_id")

    status_parser = sub.add_parser("status", help="Get run status")
    status_parser.add_argument("run_id")

    logs_parser = sub.add_parser("logs", help="List run events")
    logs_parser.add_argument("run_id")

    webhook_parser = sub.add_parser("webhook", help="Webhook operations")
    webhook_sub = webhook_parser.add_subparsers(dest="webhook_command", required=True)

    register_parser = webhook_sub.add_parser("register", help="Register a webhook channel and generate its secret")
    register_parser.add_argument("webhook", help="Webhook channel name")

    remove_parser = webhook_sub.add_parser("remove", help="Remove a webhook channel registration")
    remove_parser.add_argument("webhook", help="Webhook channel name")

    receive_parser = webhook_sub.add_parser("receive", help="Receive a webhook payload into the runtime")
    receive_parser.add_argument("webhook", help="Webhook channel (e.g. github-pr-merged)")
    receive_parser.add_argument("key", help="Webhook correlation key")
    receive_parser.add_argument("--json", dest="json_inline", help="JSON payload string")
    receive_parser.add_argument("--json-file", help="Path to JSON payload file")
    receive_parser.add_argument("--dedup-key", help="Stable deduplication key for idempotent webhook delivery")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    container = build_runtime_container()
    controller = RuntimeController(
        bootstrap_service=container.bootstrap_service,
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
            run_result = controller.run(
                skill_ref,
                inputs,
                skill_source=skill_source,
                param_run_id=args.run_id,
            )
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1

        run_result, exit_code = _maybe_start_webhooks(args, controller, container.settings, run_result)
        if args.logs and "logs" not in run_result:
            run_result["logs"] = controller.logs(run_result["run_id"])
        print(json.dumps(run_result, indent=2))
        return exit_code

    if args.command == "resume":
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

    if args.command == "webhook" and args.webhook_command == "receive":
        payload = _load_json_payload(args.json_inline, args.json_file)
        result = controller.receive_webhook(args.webhook, args.key, payload, dedup_key=args.dedup_key)
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
