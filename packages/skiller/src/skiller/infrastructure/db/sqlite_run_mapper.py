import json
import sqlite3
from typing import Any

from skiller.domain.run.run_context_model import RunContext
from skiller.domain.run.run_model import Run, RunAgent


def build_run_from_row(row: sqlite3.Row) -> Run:
    snapshot = json.loads(row["snapshot_json"])
    if not isinstance(snapshot, dict):
        snapshot = {}
    inputs_dict = json.loads(row["inputs_json"])
    if not isinstance(inputs_dict, dict):
        inputs_dict = {}
    step_executions_dict = json.loads(row["step_executions_json"])
    if not isinstance(step_executions_dict, dict):
        step_executions_dict = {}
    steering_queue = json.loads(row["steering_queue_json"])
    if not isinstance(steering_queue, list):
        steering_queue = []
    agents = _agents_from_json(row["agents_json"])

    return Run(
        id=str(row["id"]),
        source=row["source"],
        ref=row["ref"],
        snapshot=snapshot,
        status=row["status"],
        current=(str(row["current"]) if row["current"] is not None else None),
        context=build_context(
            inputs=inputs_dict,
            step_executions=step_executions_dict,
            steering_queue=steering_queue,
            cancel_reason=row["cancel_reason"],
        ),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        agents=agents,
    )


def _agents_from_json(raw_agents: object) -> dict[str, RunAgent]:
    if not isinstance(raw_agents, str) or not raw_agents.strip():
        return {}
    try:
        parsed = json.loads(raw_agents)
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}

    agents: dict[str, RunAgent] = {}
    for raw_agent_id, raw_agent in parsed.items():
        agent_id = str(raw_agent_id).strip()
        if not agent_id or not isinstance(raw_agent, dict):
            continue
        context_id = raw_agent.get("context_id")
        agents[agent_id] = RunAgent(
            agent_id=agent_id,
            context_id=context_id if isinstance(context_id, str) else None,
        )
    return agents


def build_context(
    *,
    inputs: dict[str, Any],
    step_executions: dict[str, Any],
    steering_queue: list[dict[str, Any]] | list[str],
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
        steering_queue=RunContext.from_dict(
            {
                "steering_queue": steering_queue if isinstance(steering_queue, list) else [],
            }
        ).steering_queue,
    )
    if isinstance(cancel_reason, str) and cancel_reason.strip():
        context.cancel_reason = cancel_reason
    return context
