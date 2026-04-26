import json
import sqlite3
from typing import Any

from skiller.domain.run.run_context_model import RunContext
from skiller.domain.run.run_model import Run


def build_run_from_row(row: sqlite3.Row) -> Run:
    skill_snapshot = json.loads(row["skill_snapshot_json"])
    if not isinstance(skill_snapshot, dict):
        skill_snapshot = {}
    inputs_dict = json.loads(row["inputs_json"])
    if not isinstance(inputs_dict, dict):
        inputs_dict = {}
    step_executions_dict = json.loads(row["step_executions_json"])
    if not isinstance(step_executions_dict, dict):
        step_executions_dict = {}
    steering_messages = json.loads(row["steering_messages_json"])
    if not isinstance(steering_messages, list):
        steering_messages = []

    return Run(
        id=str(row["id"]),
        skill_source=row["skill_source"],
        skill_ref=row["skill_ref"],
        skill_snapshot=skill_snapshot,
        status=row["status"],
        current=(str(row["current"]) if row["current"] is not None else None),
        context=build_context(
            inputs=inputs_dict,
            step_executions=step_executions_dict,
            steering_messages=steering_messages,
            cancel_reason=row["cancel_reason"],
        ),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def build_context(
    *,
    inputs: dict[str, Any],
    step_executions: dict[str, Any],
    steering_messages: list[str],
    cancel_reason: str | None,
) -> RunContext:
    context = RunContext(
        inputs=inputs,
        step_executions=RunContext.from_dict(
            {
                "inputs": {},
                "step_executions": (
                    step_executions if isinstance(step_executions, dict) else {}
                ),
            }
        ).step_executions,
        steering_messages=steering_messages if isinstance(steering_messages, list) else [],
    )
    if isinstance(cancel_reason, str) and cancel_reason.strip():
        context.cancel_reason = cancel_reason
    return context
