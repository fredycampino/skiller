import argparse
import json
from pathlib import Path

from runtime.application.factory import build_runtime_container


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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent", description="Agent Runtime POC CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init-db", help="Initialize SQLite schema")

    run_parser = sub.add_parser("run", help="Start a run with a skill")
    run_parser.add_argument("skill", help="Skill name (without extension)")
    run_parser.add_argument("--arg", action="append", default=[], help="Input pair key=value")

    status_parser = sub.add_parser("status", help="Get run status")
    status_parser.add_argument("run_id")

    logs_parser = sub.add_parser("logs", help="List run events")
    logs_parser.add_argument("run_id")

    webhook_parser = sub.add_parser("webhook", help="Webhook operations")
    webhook_sub = webhook_parser.add_subparsers(dest="webhook_command", required=True)

    inject_parser = webhook_sub.add_parser("inject", help="Inject a webhook payload into the runtime")
    inject_parser.add_argument("wait_key", help="Webhook wait key (e.g. webhook.merge.xyz)")
    inject_parser.add_argument("--json", dest="json_inline", help="JSON payload string")
    inject_parser.add_argument("--json-file", help="Path to JSON payload file")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    container = build_runtime_container()
    settings = container.settings
    bootstrap = container.bootstrap
    runtime = container.runtime
    query = container.query
    bootstrap.initialize()

    if args.command == "init-db":
        print(f"DB initialized: {settings.db_path}")
        return 0

    if args.command == "run":
        inputs = _parse_key_value(args.arg)
        run_id = runtime.start_run(args.skill, inputs)
        print(run_id)
        return 0

    if args.command == "status":
        run = query.get_status(args.run_id)
        if run is None:
            print("Run not found")
            return 1
        print(json.dumps(run, indent=2))
        return 0

    if args.command == "logs":
        events = query.get_logs(args.run_id)
        print(json.dumps(events, indent=2))
        return 0

    if args.command == "webhook" and args.webhook_command == "inject":
        payload = _load_json_payload(args.json_inline, args.json_file)
        resumed_runs = runtime.handle_webhook(args.wait_key, payload)
        print(json.dumps({"wait_key": args.wait_key, "matched_runs": resumed_runs}, indent=2))
        return 0

    parser.print_help()
    return 1
