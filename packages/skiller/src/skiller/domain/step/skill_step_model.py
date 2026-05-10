from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from skiller.domain.step.step_type import StepType


@dataclass(frozen=True)
class SkillStep:
    step_id: str
    step_type: StepType
    body: dict[str, Any]


def parse_skill_step(raw_step: object) -> SkillStep:
    if not isinstance(raw_step, dict):
        raise ValueError("invalid step entry")

    if "id" in raw_step or "type" in raw_step:
        raise ValueError("legacy step shape is not supported")

    primary_keys = [key for key in raw_step if _is_step_type_key(key)]
    if len(primary_keys) != 1:
        raise ValueError("step requires exactly one primary header")

    primary_key = primary_keys[0]
    step_id = str(raw_step.get(primary_key, "")).strip()
    if not step_id:
        raise ValueError("step requires non-empty step id")

    step_type = StepType(primary_key)
    body = {key: value for key, value in raw_step.items() if key != primary_key}
    return SkillStep(step_id=step_id, step_type=step_type, body=body)


def find_skill_step(raw_steps: object, step_id: str) -> tuple[int, SkillStep]:
    parsed_steps = parse_skill_steps(raw_steps)

    match_index = -1
    match_step: SkillStep | None = None

    for index, parsed in enumerate(parsed_steps):
        if parsed.step_id != step_id:
            continue
        if match_step is not None:
            raise ValueError(f"duplicate step id '{step_id}'")
        match_index = index
        match_step = parsed

    if match_step is None:
        raise ValueError(f"step '{step_id}' was not found")

    return match_index, match_step


def parse_skill_steps(raw_steps: object) -> list[SkillStep]:
    if not isinstance(raw_steps, list):
        raise ValueError("invalid steps list")

    parsed_steps: list[SkillStep] = []
    seen_step_ids: set[str] = set()

    for raw_step in raw_steps:
        parsed = parse_skill_step(raw_step)
        if parsed.step_id in seen_step_ids:
            raise ValueError(f"duplicate step id '{parsed.step_id}'")
        seen_step_ids.add(parsed.step_id)
        parsed_steps.append(parsed)

    return parsed_steps


def validate_skill_snapshot(raw_skill: object) -> dict[str, Any]:
    if not isinstance(raw_skill, dict):
        raise ValueError("Invalid skill format. Expected an object.")

    start_step_id = str(raw_skill.get("start", "")).strip()
    if not start_step_id:
        raise ValueError("Skill requires non-empty root 'start'")

    raw_steps = raw_skill.get("steps", [])
    parse_skill_steps(raw_steps)
    find_skill_step(raw_steps, start_step_id)
    return raw_skill


def _is_step_type_key(value: object) -> bool:
    if not isinstance(value, str):
        return False
    normalized = value.strip()
    return normalized in {item.value for item in StepType}
