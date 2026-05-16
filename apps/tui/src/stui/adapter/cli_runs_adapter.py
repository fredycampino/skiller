from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from stui.adapter.cli_invoker import CliInvoker
from stui.port.runs_port import RunsPortItem


@dataclass(frozen=True)
class CliRunsAdapter:
    invoker: CliInvoker = field(default_factory=CliInvoker)

    def list_runs(
        self,
        *,
        limit: int = 20,
        statuses: list[str] | None = None,
    ) -> list[RunsPortItem]:
        args = ["runs", "--limit", str(limit)]
        for status in statuses or []:
            normalized_status = status.strip()
            if normalized_status:
                args.extend(["--status", normalized_status])

        payload = _run_json_command(self.invoker, *args)
        if not isinstance(payload, list):
            raise RuntimeError("runs command returned invalid payload")
        return [_parse_run_list_item(item) for item in payload if isinstance(item, dict)]


def _run_json_command(invoker: CliInvoker, *args: str) -> Any:
    completed = invoker.run(*args)

    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "runtime command failed"
        raise RuntimeError(detail)

    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("runtime command returned invalid JSON") from exc

    return payload

def _parse_run_list_item(payload: dict[str, Any]) -> RunsPortItem:
    return RunsPortItem(
        id=str(payload.get("id", "")).strip(),
        source=str(payload.get("source", "")).strip(),
        ref=str(payload.get("ref", "")).strip(),
        status=str(payload.get("status", "")).strip(),
        current=_optional_text(payload.get("current")),
        created_at=str(payload.get("created_at", "")).strip(),
        updated_at=str(payload.get("updated_at", "")).strip(),
        wait_type=_optional_text(payload.get("wait_type")),
        wait_detail=_optional_text(payload.get("wait_detail")),
    )


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None
