from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
from pathlib import Path
from typing import Any

COMPACT_DIR = Path("packages/skiller/tests/e2e-agent/compact")
WORKSPACE_DIR = COMPACT_DIR / "workspace"
EXPECTED_ECHO_COMMAND = "echo compact-e2e-tool"
EXPECTED_ECHO_OUTPUT = "compact-e2e-tool"

EXPECTED_FINALS = [
    "COMPACT-E2E-HOLA",
    "COMPACT-E2E-ECHO",
    "COMPACT-E2E-ECHO-AGAIN",
    "COMPACT-E2E-PREVIOUS-ECHO",
]
EXPECTED_TOOL_CALLS = [EXPECTED_ECHO_COMMAND, EXPECTED_ECHO_COMMAND]
EXPECTED_TOOL_RESULTS = [EXPECTED_ECHO_OUTPUT, EXPECTED_ECHO_OUTPUT]
EXPECTED_USAGE_MARKERS = [2, 4, 7, 9, 12, 14]
EXPECTED_CONTEXT = [
    (1, "user_message", None, False, False, True),
    (2, "assistant_message", "final", True, True, True),
    (3, "user_message", None, False, False, True),
    (4, "assistant_message", "tool_calls", True, True, False),
    (5, "tool_call", None, False, False, False),
    (6, "tool_result", None, False, False, False),
    (7, "assistant_message", "final", True, True, True),
    (8, "user_message", None, False, False, True),
    (9, "assistant_message", "tool_calls", True, True, False),
    (10, "tool_call", None, False, False, False),
    (11, "tool_result", None, False, False, False),
    (12, "assistant_message", "final", True, True, True),
    (13, "user_message", None, False, False, True),
    (14, "assistant_message", "final", True, True, True),
]
EXPECTED_ROLES = [
    ["system", "user"],
    ["system", "user", "assistant_final", "user"],
    ["system", "user", "assistant_final", "user", "assistant_tool_calls", "tool_result"],
    [
        "system",
        "user",
        "assistant_final",
        "user",
        "assistant_tool_calls",
        "tool_result",
        "assistant_final",
        "user",
    ],
    [
        "system",
        "user",
        "assistant_final",
        "user",
        "assistant_tool_calls",
        "tool_result",
        "assistant_final",
        "user",
        "assistant_tool_calls",
        "tool_result",
    ],
    [
        "system",
        "user",
        "assistant_final",
        "user",
        "assistant_final",
        "user",
        "assistant_tool_calls",
        "tool_result",
        "assistant_final",
        "user",
    ],
]


def role_label(message: dict[str, Any]) -> str:
    role = message["role"]
    if role == "assistant" and message.get("tool_calls"):
        return "assistant_tool_calls"
    if role == "assistant":
        return "assistant_final"
    if role == "tool":
        return "tool_result"
    return str(role)


def pass_fail(value: bool) -> str:
    return "PASS" if value else "FAIL"


def markdown_cell(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value).replace("|", "\\|")


def read_status(status_path: Path) -> str:
    text = status_path.read_text(encoding="utf-8").strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return text
    return str(payload.get("status", payload))


def tool_call_summary(body: dict[str, Any]) -> str:
    args = body["args"]
    command = args.get("command")
    if isinstance(command, str):
        return command
    path = args.get("path")
    if isinstance(path, str):
        return path
    return json.dumps(args, sort_keys=True)


def tool_result_summary(body: dict[str, Any]) -> str:
    data = body["data"]
    path = data.get("path")
    if isinstance(path, str):
        return path
    stdout = data.get("stdout")
    if isinstance(stdout, str):
        return stdout.strip()
    text = body.get("text")
    if isinstance(text, str):
        return text.strip()
    return json.dumps(data, sort_keys=True)


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def event_summary(db_path: Path) -> tuple[list[str], list[str], list[str]]:
    conn = connect(db_path)
    rows = conn.execute(
        """
        SELECT event_type, body_json
        FROM log_events
        WHERE event_type IN (
          'AGENT_FINAL_ASSISTANT_MESSAGE',
          'AGENT_TOOL_CALL',
          'AGENT_TOOL_RESULT'
        )
        ORDER BY sequence
        """
    ).fetchall()

    finals: list[str] = []
    tool_calls: list[str] = []
    tool_results: list[str] = []
    for row in rows:
        payload = json.loads(row["body_json"])
        body = payload["body"]
        if row["event_type"] == "AGENT_FINAL_ASSISTANT_MESSAGE":
            finals.append(body["text"])
        elif row["event_type"] == "AGENT_TOOL_CALL":
            tool_calls.append(tool_call_summary(body))
        elif row["event_type"] == "AGENT_TOOL_RESULT":
            tool_results.append(tool_result_summary(body))
    return finals, tool_calls, tool_results


def context_rows(db_path: Path) -> list[sqlite3.Row]:
    conn = connect(db_path)
    return conn.execute(
        """
        SELECT sequence,
               entry_type,
               message_type,
               delta_tokens,
               delta_compact_tokens,
               window_start_sequence,
               window_base,
               usage_json
        FROM agent_context_entries
        ORDER BY sequence ASC
        """
    ).fetchall()


def actual_context(rows: list[sqlite3.Row]) -> list[tuple[int, str, str | None, bool, bool, bool]]:
    actual: list[tuple[int, str, str | None, bool, bool, bool]] = []
    for row in rows:
        actual.append(
            (
                row["sequence"],
                row["entry_type"],
                row["message_type"],
                row["usage_json"] is not None,
                row["delta_tokens"] is not None,
                row["delta_compact_tokens"] is not None,
            )
        )
    return actual


def marker_rows(rows: list[sqlite3.Row]) -> list[dict[str, object]]:
    markers: list[dict[str, object]] = []
    actual = actual_context(rows)
    for index, row in enumerate(rows):
        usage = json.loads(row["usage_json"]) if row["usage_json"] is not None else None
        prompt_tokens = usage.get("prompt_tokens") if usage is not None else None
        prunable = (
            row["entry_type"] in ("tool_call", "tool_result")
            or row["entry_type"] == "assistant_message"
            and row["message_type"] == "tool_calls"
        )
        expected_row = EXPECTED_CONTEXT[index] if index < len(EXPECTED_CONTEXT) else None
        markers.append(
            {
                "sequence": row["sequence"],
                "entry_type": row["entry_type"],
                "message_type": row["message_type"],
                "usage_json": row["usage_json"] is not None,
                "prompt_tokens": prompt_tokens,
                "delta_tokens": row["delta_tokens"],
                "delta_compact_tokens": row["delta_compact_tokens"],
                "prunable": prunable,
                "result": expected_row == actual[index],
            }
        )
    return markers


def request_roles(log_dir: Path) -> list[list[str]]:
    roles: list[list[str]] = []
    for path in sorted(log_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        request = payload["request"]
        roles.append([role_label(message) for message in request["messages"]])
    return roles


def prompt_tokens_from_usage(raw: str | None) -> int | None:
    if raw is None:
        return None
    usage = json.loads(raw)
    prompt_tokens = usage.get("prompt_tokens")
    return prompt_tokens if isinstance(prompt_tokens, int) else None


def context_snapshot(db_path: Path) -> list[dict[str, object]]:
    rows = context_rows(db_path)
    return [
        {
            "sequence": row["sequence"],
            "entry_type": row["entry_type"],
            "message_type": row["message_type"],
            "usage_json": row["usage_json"] is not None,
            "prompt_tokens": prompt_tokens_from_usage(row["usage_json"]),
            "delta_tokens": row["delta_tokens"],
            "delta_compact_tokens": row["delta_compact_tokens"],
            "window_start_sequence": row["window_start_sequence"],
            "window_base": bool(row["window_base"]),
        }
        for row in rows
    ]


def request_snapshot(log_dir: Path) -> list[dict[str, object]]:
    requests: list[dict[str, object]] = []
    for path in sorted(log_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        request = payload["request"]
        response = payload["response"]
        response_usage = response.get("usage") if isinstance(response, dict) else None
        response_prompt_tokens = (
            response_usage.get("prompt_tokens")
            if isinstance(response_usage, dict)
            else None
        )
        requests.append(
            {
                "file": path.name,
                "sequence": payload["sequence"],
                "roles": [role_label(message) for message in request["messages"]],
                "response": payload["response"] is not None,
                "response_prompt_tokens": response_prompt_tokens,
                "error": payload["error"],
            }
        )
    return requests


def print_snapshot(db_path: Path, log_dir: Path) -> None:
    print(
        json.dumps(
            {
                "context": context_snapshot(db_path),
                "requests": request_snapshot(log_dir),
            },
            indent=2,
        )
    )


def prepare() -> None:
    shutil.rmtree(WORKSPACE_DIR, ignore_errors=True)
    WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
    (COMPACT_DIR / "reports").mkdir(parents=True, exist_ok=True)


def write_report(
    *,
    run_id: str,
    db_path: Path,
    log_dir: Path,
    status_path: Path,
    report_path: Path,
) -> None:
    finals, tool_calls, tool_results = event_summary(db_path)
    rows = context_rows(db_path)
    actual = actual_context(rows)
    markers = marker_rows(rows)
    usage_marker_sequences = [
        row["sequence"]
        for row in markers
        if row["usage_json"]
    ]
    roles = request_roles(log_dir)

    checks = [
        ("final assistant messages", "4", str(len(finals)), finals == EXPECTED_FINALS),
        ("tool calls", "2", str(len(tool_calls)), tool_calls == EXPECTED_TOOL_CALLS),
        (
            "tool results",
            "2",
            str(len(tool_results)),
            tool_results == EXPECTED_TOOL_RESULTS,
        ),
        (
            "context entries",
            str(len(EXPECTED_CONTEXT)),
            str(len(rows)),
            actual == EXPECTED_CONTEXT,
        ),
        (
            "usage markers",
            ",".join(str(item) for item in EXPECTED_USAGE_MARKERS),
            ",".join(str(item) for item in usage_marker_sequences),
            usage_marker_sequences == EXPECTED_USAGE_MARKERS,
        ),
        ("request logs", "6", str(len(roles)), roles == EXPECTED_ROLES),
    ]

    lines = [
        "## Compact Context E2E Results",
        "",
        f"- RUN_ID: `{run_id}`",
        f"- Final status: `{read_status(status_path)}`",
        "- Workspace cleaned: `pending`",
        "",
        "| check | expected | actual | result |",
        "|---|---:|---:|---|",
    ]
    for name, expected, actual_value, result in checks:
        lines.append(f"| {name} | `{expected}` | `{actual_value}` | `{pass_fail(result)}` |")

    lines.extend(
        [
            "",
            "## Context Markers",
            "",
            "| sequence | entry_type | message_type | usage_json | prompt_tokens | "
            "delta_tokens | delta_compact_tokens | prunable | result |",
            "|---:|---|---|---|---:|---:|---:|---|---|",
        ]
    )
    for row in markers:
        lines.append(
            "| "
            + " | ".join(
                [
                    markdown_cell(row["sequence"]),
                    markdown_cell(row["entry_type"]),
                    markdown_cell(row["message_type"]),
                    markdown_cell(row["usage_json"]),
                    markdown_cell(row["prompt_tokens"]),
                    markdown_cell(row["delta_tokens"]),
                    markdown_cell(row["delta_compact_tokens"]),
                    markdown_cell(row["prunable"]),
                    pass_fail(bool(row["result"])),
                ]
            )
            + " |"
        )

    lines.extend(["", "## Final Messages", ""])
    for final in finals:
        lines.append(f"- `{final}`")

    lines.extend(
        [
            "",
            "## Request Windows",
            "",
            "| request | roles | result |",
            "|---:|---|---|",
        ]
    )
    for index, row_roles in enumerate(roles, 1):
        expected = EXPECTED_ROLES[index - 1] if index <= len(EXPECTED_ROLES) else []
        lines.append(
            f"| {index} | `{' -> '.join(row_roles)}` | {pass_fail(row_roles == expected)} |"
        )

    failed = [name for name, _, _, result in checks if not result]
    note = "none" if not failed else "failed checks: " + ", ".join(failed)
    lines.extend(["", "## Notes", "", f"- {note}", ""])

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(report_path)


def mark_cleaned(report_path: Path) -> None:
    text = report_path.read_text(encoding="utf-8")
    text = text.replace("- Workspace cleaned: `pending`", "- Workspace cleaned: `yes`")
    report_path.write_text(text, encoding="utf-8")


def cleanup(report_path: Path) -> None:
    shutil.rmtree(WORKSPACE_DIR, ignore_errors=True)
    mark_cleaned(report_path)
    print(report_path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("prepare")

    snapshot_parser = subparsers.add_parser("snapshot")
    snapshot_parser.add_argument("--db-path", required=True, type=Path)
    snapshot_parser.add_argument("--log-dir", required=True, type=Path)

    write_report_parser = subparsers.add_parser("write-report")
    write_report_parser.add_argument("--run-id", required=True)
    write_report_parser.add_argument("--db-path", required=True, type=Path)
    write_report_parser.add_argument("--log-dir", required=True, type=Path)
    write_report_parser.add_argument("--status-path", required=True, type=Path)
    write_report_parser.add_argument("--report-path", required=True, type=Path)

    cleanup_parser = subparsers.add_parser("cleanup")
    cleanup_parser.add_argument("--report-path", required=True, type=Path)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "prepare":
        prepare()
    elif args.command == "snapshot":
        print_snapshot(args.db_path, args.log_dir)
    elif args.command == "write-report":
        write_report(
            run_id=args.run_id,
            db_path=args.db_path,
            log_dir=args.log_dir,
            status_path=args.status_path,
            report_path=args.report_path,
        )
    elif args.command == "cleanup":
        cleanup(args.report_path)


if __name__ == "__main__":
    main()
