"""Reproduce Bedrock streaming behaviour when a tool_use input exceeds max_tokens.

The probe asks the real Bedrock streaming endpoint to call a ``shell`` tool whose
``command`` payload is sized so the resulting ``input`` JSON would exceed
``max_tokens``. It records only metadata: tool call names, the byte length of
``arguments_json``, whether it parses, whether ``command`` is present and its
length. No command text, message content, credentials, or paths are written.

When ``BEDROCK_PROBE_CAPTURE_DIR`` is set, the full Bedrock request and response
payload is dumped to that directory, one JSON file per cell. This is what the
formatter asked for: it lets us inspect the exact JSON Bedrock returns when a
tool_use input is truncated by ``max_tokens``.

Run without ``--live`` to validate the source and inspect the request layout
without contacting Bedrock.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from skiller.domain.agent.llm.model import (
    LLMSystemMessage,
    LLMUserMessage,
)
from skiller.domain.agent.llm.provider_bedrock import BedrockLLMRequest
from skiller.domain.tool.tool_contract import (
    ToolDefinition,
    ToolInput,
    ToolRequest,
    ToolRequestResult,
    ToolSchema,
)
from skiller.infrastructure.llm.bedrock.bedrock_mapper import BedrockMapper
from skiller.infrastructure.llm.bedrock.bedrock_request_logger import (
    BedrockFileLLMRequestLogger,
)
from skiller.infrastructure.llm.bedrock.bedrock_streaming_port import (
    BedrockStreamingLLMPort,
)
from skiller.infrastructure.llm.mapper.llm_usage_mapper import DefaultLLMUsageMapper

DEFAULT_PAYLOAD_SIZES = (64, 128, 256, 512, 1024)
DEFAULT_MAX_TOKENS = 256
DEFAULT_MODEL = "us.anthropic.claude-opus-4-6-v1"
DEFAULT_PROFILE = "default"
DEFAULT_TIMEOUT_SECONDS = 45.0
DEFAULT_ITERATIONS = 1
CAPTURE_DIR_ENV = "BEDROCK_PROBE_CAPTURE_DIR"


@dataclass(frozen=True)
class _ProbeModel:
    value: str
    model_context_window_tokens: int


class ShellSmokeTool(ToolDefinition[ToolRequest]):
    name = "shell"
    description = "Run a shell command."

    def schema(self) -> ToolSchema:
        return ToolSchema(
            value={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Command to run.",
                    },
                },
                "required": ["command"],
                "additionalProperties": False,
            },
        )

    def request(self, input: ToolInput) -> ToolRequestResult[ToolRequest]:
        return ToolRequestResult.valid(ToolRequest())


@dataclass(frozen=True)
class BedrockTraceWriter:
    path: Path

    def write(self, event: str, **fields: object) -> None:
        record = {"timestamp": _utc_now_iso(), "event": event, **fields}
        line = json.dumps(record, ensure_ascii=False, sort_keys=True)
        with self.path.open("a", encoding="utf-8") as file:
            file.write(line)
            file.write("\n")
            file.flush()


class BedrockProbeClient(Protocol):
    def generate(self, request: BedrockLLMRequest) -> object: ...


@dataclass(frozen=True)
class ProbeSettings:
    max_tokens: int
    payload_sizes: tuple[int, ...]
    iterations: int
    model: str
    profile: str
    timeout_seconds: float
    trace_file: Path
    live: bool
    capture_dir: Path | None


def parse_payload_sizes(raw: str) -> tuple[int, ...]:
    sizes: list[int] = []
    for piece in raw.split(","):
        text = piece.strip()
        if not text:
            continue
        try:
            value = int(text)
        except ValueError as exc:
            raise SystemExit(f"invalid payload size: {text!r}") from exc
        if value <= 0:
            raise SystemExit(f"payload size must be positive: {value}")
        sizes.append(value)
    if not sizes:
        raise SystemExit("at least one payload size is required")
    return tuple(sizes)


def parse_args(argv: Iterable[str] | None = None) -> ProbeSettings:
    parser = argparse.ArgumentParser(
        description=(
            "Probe Bedrock streaming tool_use behaviour when arguments_json "
            "would exceed max_tokens."
        ),
    )
    parser.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    parser.add_argument(
        "--payload-sizes",
        type=parse_payload_sizes,
        default=DEFAULT_PAYLOAD_SIZES,
        help="Comma-separated payload sizes in characters (default: 64,128,256,512,1024).",
    )
    parser.add_argument("--iterations", type=int, default=DEFAULT_ITERATIONS)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument(
        "--profile",
        default=os.environ.get("AGENT_BEDROCK_PROFILE", DEFAULT_PROFILE),
        help="Bedrock AWS profile (default: AGENT_BEDROCK_PROFILE or 'default').",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=float(
            os.environ.get("AGENT_BEDROCK_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS)
        ),
        help="Per-request timeout in seconds (default: AGENT_BEDROCK_TIMEOUT_SECONDS or 45).",
    )
    parser.add_argument(
        "--trace-file",
        type=Path,
        default=None,
        help="JSONL output path. Defaults to /tmp/skiller-bedrock-probe-<uuid>.jsonl.",
    )
    parser.add_argument(
        "--capture-dir",
        type=Path,
        default=Path(os.environ[CAPTURE_DIR_ENV]) if CAPTURE_DIR_ENV in os.environ else None,
        help=(
            "Directory to dump full Bedrock request/response JSON per cell. "
            f"Default: ${CAPTURE_DIR_ENV} if set, otherwise not captured."
        ),
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Actually call the Bedrock streaming endpoint and consume account quota.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.max_tokens <= 0:
        raise SystemExit("max_tokens must be positive")
    if args.iterations <= 0:
        raise SystemExit("iterations must be positive")
    if args.timeout_seconds <= 0:
        raise SystemExit("timeout_seconds must be positive")

    trace_file = args.trace_file
    if trace_file is None:
        trace_file = Path(f"/tmp/skiller-bedrock-probe-{uuid.uuid4().hex}.jsonl")

    return ProbeSettings(
        max_tokens=args.max_tokens,
        payload_sizes=tuple(args.payload_sizes),
        iterations=args.iterations,
        model=args.model,
        profile=args.profile,
        timeout_seconds=args.timeout_seconds,
        trace_file=trace_file,
        live=args.live,
        capture_dir=args.capture_dir,
    )


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def estimate_payload_tokens(chars: int) -> int:
    """Rough estimate: ~4 characters per token for ASCII payloads."""
    return max(1, chars // 4)


def build_request(
    *,
    model: _ProbeModel,
    max_tokens: int,
    payload_chars: int,
    log_request_file: str | None = None,
) -> BedrockLLMRequest:
    payload = "a" * payload_chars
    return BedrockLLMRequest(
        model=model,
        messages=(
            LLMSystemMessage("You must call the requested tool. Do not answer in text."),
            LLMUserMessage(
                f"Call the shell tool with a command whose command value is exactly "
                f"the literal string 'echo {payload}' (no surrounding quotes, "
                f"echo, space, then {payload_chars} 'a' characters)."
            ),
        ),
        max_tokens=max_tokens,
        tools=(ShellSmokeTool(),),
        log_request_file=log_request_file,
        log_override_file=log_request_file is not None,
    )


def inspect_response(response: object) -> dict[str, object]:
    ok = bool(getattr(response, "ok", False))
    finish_reason = getattr(response, "finish_reason", None)
    error = getattr(response, "error", None)
    error_code = getattr(response, "error_code", None)
    tool_calls = tuple(getattr(response, "tool_calls", ()) or ())
    usage = getattr(response, "usage", None)

    cells: list[dict[str, object]] = []
    for call in tool_calls:
        arguments_json = getattr(call.function, "arguments_json", "")
        args_len = len(arguments_json)
        args_empty = args_len == 0 or arguments_json == "{}"
        try:
            parsed = json.loads(arguments_json) if arguments_json else {}
        except json.JSONDecodeError:
            parsed = None
        parses = parsed is not None
        command_value = None
        command_chars = None
        if isinstance(parsed, dict):
            command_value_obj = parsed.get("command")
            if isinstance(command_value_obj, str):
                command_value = True
                command_chars = len(command_value_obj)
            else:
                command_value = False
        cells.append(
            {
                "tool_name": getattr(call.function, "name", None),
                "arguments_json_len": args_len,
                "arguments_json_empty": args_empty,
                "arguments_json_parses": parses,
                "arguments_json_has_command": command_value,
                "arguments_json_command_chars": command_chars,
            },
        )

    usage_summary: dict[str, object] | None = None
    if usage is not None:
        usage_summary = {
            "prompt_tokens": getattr(usage, "prompt_tokens", None),
            "output_tokens": getattr(usage, "output_tokens", None),
            "total_tokens": getattr(usage, "total_tokens", None),
        }

    return {
        "ok": ok,
        "finish_reason": finish_reason,
        "error": error,
        "error_code": error_code,
        "tool_call_count": len(cells),
        "tool_calls": cells,
        "usage": usage_summary,
    }


def build_dry_run_grid(settings: ProbeSettings) -> list[dict[str, object]]:
    grid: list[dict[str, object]] = []
    for payload_size in settings.payload_sizes:
        for iteration in range(1, settings.iterations + 1):
            grid.append(
                {
                    "iteration": iteration,
                    "max_tokens": settings.max_tokens,
                    "payload_chars": payload_size,
                    "payload_estimated_tokens": estimate_payload_tokens(payload_size),
                },
            )
    return grid


def execute_real(
    *,
    settings: ProbeSettings,
    client: BedrockProbeClient,
    trace_writer: BedrockTraceWriter,
) -> list[dict[str, object]]:
    model = _ProbeModel(settings.model, 200000)
    capture_dir = settings.capture_dir
    observations: list[dict[str, object]] = []
    for payload_size in settings.payload_sizes:
        for iteration in range(1, settings.iterations + 1):
            capture_path: str | None = None
            if capture_dir is not None:
                capture_dir.mkdir(parents=True, exist_ok=True)
                capture_path = str(
                    capture_dir / f"max{settings.max_tokens}_p{payload_size}_i{iteration}.json"
                )
            request = build_request(
                model=model,
                max_tokens=settings.max_tokens,
                payload_chars=payload_size,
                log_request_file=capture_path,
            )
            trace_writer.write(
                "request_sent",
                iteration=iteration,
                max_tokens=settings.max_tokens,
                payload_chars=payload_size,
                payload_estimated_tokens=estimate_payload_tokens(payload_size),
                capture_path=capture_path,
            )
            started = time.monotonic()
            try:
                response = client.generate(request)
            except Exception as exc:  # noqa: BLE001
                trace_writer.write(
                    "response_exception",
                    iteration=iteration,
                    max_tokens=settings.max_tokens,
                    payload_chars=payload_size,
                    elapsed_ms=_elapsed_ms(started),
                    exception_type=type(exc).__name__,
                    exception_message=str(exc),
                )
                observations.append(
                    {
                        "iteration": iteration,
                        "max_tokens": settings.max_tokens,
                        "payload_chars": payload_size,
                        "ok": False,
                        "error_code": "exception",
                        "error": f"{type(exc).__name__}: {exc}",
                    },
                )
                continue

            observation = inspect_response(response)
            observation.update(
                {
                    "iteration": iteration,
                    "max_tokens": settings.max_tokens,
                    "payload_chars": payload_size,
                    "payload_estimated_tokens": estimate_payload_tokens(payload_size),
                    "elapsed_ms": _elapsed_ms(started),
                    "capture_path": capture_path,
                },
            )
            trace_writer.write(
                "response_observed",
                iteration=iteration,
                max_tokens=settings.max_tokens,
                payload_chars=payload_size,
                elapsed_ms=observation["elapsed_ms"],
                ok=observation["ok"],
                finish_reason=observation["finish_reason"],
                tool_call_count=observation["tool_call_count"],
                tool_calls=observation["tool_calls"],
                usage=observation["usage"],
                error_code=observation["error_code"],
                error=observation["error"],
                capture_path=capture_path,
            )
            observations.append(observation)
    return observations


def _elapsed_ms(started: float) -> int:
    return round((time.monotonic() - started) * 1000)


def summarize(observations: list[dict[str, object]]) -> dict[str, object]:
    cells: dict[tuple[int, int], list[dict[str, object]]] = {}
    for entry in observations:
        key = (int(entry["max_tokens"]), int(entry["payload_chars"]))
        cells.setdefault(key, []).append(entry)

    rows: list[dict[str, object]] = []
    for (max_tokens, payload_chars), entries in sorted(cells.items()):
        rows.append(
            {
                "max_tokens": max_tokens,
                "payload_chars": payload_chars,
                "runs": len(entries),
                "ok_count": sum(1 for e in entries if e.get("ok")),
                "truncated_count": sum(
                    1 for e in entries if e.get("finish_reason") == "max_tokens"
                ),
                "tool_use_count": sum(
                    1 for e in entries if e.get("finish_reason") == "tool_use"
                ),
                "end_turn_count": sum(
                    1 for e in entries if e.get("finish_reason") == "end_turn"
                ),
                "tool_call_count_total": sum(
                    int(e.get("tool_call_count", 0) or 0) for e in entries
                ),
                "empty_input_count": sum(
                    1
                    for e in entries
                    for call in (e.get("tool_calls") or [])
                    if call.get("arguments_json_empty")
                ),
                "parses_count": sum(
                    1
                    for e in entries
                    for call in (e.get("tool_calls") or [])
                    if call.get("arguments_json_parses")
                ),
                "error_count": sum(1 for e in entries if e.get("error_code")),
            },
        )
    return {"rows": rows}


def print_dry_run(settings: ProbeSettings) -> None:
    grid = build_dry_run_grid(settings)
    summary = {
        "status": "DRY_RUN",
        "max_tokens": settings.max_tokens,
        "payload_sizes": list(settings.payload_sizes),
        "iterations": settings.iterations,
        "model": settings.model,
        "profile": settings.profile,
        "timeout_seconds": settings.timeout_seconds,
        "trace_file": str(settings.trace_file),
        "capture_dir": str(settings.capture_dir) if settings.capture_dir else None,
        "grid": grid,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))


def print_run_summary(
    settings: ProbeSettings,
    observations: list[dict[str, object]],
) -> None:
    summary = {
        "status": "COMPLETED",
        "max_tokens": settings.max_tokens,
        "payload_sizes": list(settings.payload_sizes),
        "iterations": settings.iterations,
        "model": settings.model,
        "profile": settings.profile,
        "trace_file": str(settings.trace_file),
        "capture_dir": str(settings.capture_dir) if settings.capture_dir else None,
        "summary": summarize(observations),
    }
    print(json.dumps(summary, indent=2, sort_keys=True))


def build_client(settings: ProbeSettings) -> BedrockStreamingLLMPort:
    return BedrockStreamingLLMPort(
        profile=settings.profile,
        timeout_seconds=settings.timeout_seconds,
        request_logger=BedrockFileLLMRequestLogger(overwrite=False),
        mapper=BedrockMapper(usage_mapper=DefaultLLMUsageMapper()),
    )


def main(argv: Iterable[str] | None = None) -> int:
    settings = parse_args(argv)
    settings.trace_file.parent.mkdir(parents=True, exist_ok=True)
    settings.trace_file.write_text("", encoding="utf-8")

    writer = BedrockTraceWriter(settings.trace_file)
    writer.write(
        "probe_started",
        max_tokens=settings.max_tokens,
        payload_sizes=list(settings.payload_sizes),
        iterations=settings.iterations,
        model=settings.model,
        profile=settings.profile,
        timeout_seconds=settings.timeout_seconds,
        live=settings.live,
        capture_dir=str(settings.capture_dir) if settings.capture_dir else None,
    )

    if not settings.live:
        print_dry_run(settings)
        writer.write("probe_finished", status="DRY_RUN")
        return 0

    client = build_client(settings)
    observations = execute_real(
        settings=settings,
        client=client,
        trace_writer=writer,
    )
    print_run_summary(settings, observations)
    writer.write("probe_finished", status="COMPLETED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
