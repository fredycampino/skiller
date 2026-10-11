from collections.abc import Mapping

from skiller.domain.shared.file_reference import validate_file_reference
from skiller.domain.step.run_step_model import parse_run_steps
from skiller.domain.step.step_type import StepType


def agent_config_file(step: Mapping[str, object]) -> str | None:
    if "config" not in step:
        return None
    config = step["config"]
    if not isinstance(config, dict) or set(config) != {"file"}:
        raise ValueError("Agent config must contain exactly 'file'")
    reference = config["file"]
    if not isinstance(reference, str):
        raise ValueError("Agent config.file must be a string")
    validate_file_reference(reference)
    return reference.strip()


def snapshot_agent_config_file(snapshot: Mapping[str, object]) -> str | None:
    for step in parse_run_steps(snapshot.get("steps", [])):
        if step.step_type == StepType.AGENT:
            return agent_config_file(step.body)
    return None
