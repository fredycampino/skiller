from __future__ import annotations

import json
from dataclasses import dataclass, field

from pydantic import ValidationError

from stui.adapter.cli_invoker import CliInvoker
from stui.adapter.events.cli_log_event import CliLogEvent


@dataclass(frozen=True)
class CliLogEventAdapter:
    invoker: CliInvoker = field(default_factory=CliInvoker)

    def list(
        self,
        run_id: str,
        *,
        after_sequence: int | None = None,
        limit: int | None = None,
    ) -> list[CliLogEvent]:
        normalized_run_id = run_id.strip()
        if not normalized_run_id:
            raise RuntimeError("logs command requires run_id")

        args = ["logs", normalized_run_id]
        if after_sequence is not None:
            args.extend(["--after", str(after_sequence)])
        if limit is not None:
            args.extend(["--limit", str(limit)])

        payload = _run_json_command(self.invoker, *args)
        if not isinstance(payload, list):
            raise RuntimeError("logs command returned invalid payload")
        return [_parse_cli_log_event(item) for item in payload]


def _run_json_command(invoker: CliInvoker, *args: str) -> object:
    completed = invoker.run(*args)
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "runtime command failed"
        raise RuntimeError(detail)

    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("runtime command returned invalid JSON") from exc


def _parse_cli_log_event(value: object) -> CliLogEvent:
    try:
        return CliLogEvent.model_validate(value)
    except ValidationError as exc:
        raise RuntimeError(f"logs command returned invalid event: {exc}") from exc
