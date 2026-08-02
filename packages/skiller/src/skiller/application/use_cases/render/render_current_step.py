import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from skiller.domain.run.run_model import RunStatus
from skiller.domain.run.run_store_port import RunStorePort
from skiller.domain.step.current_step_model import CurrentStep, CurrentStepStatus
from skiller.domain.step.run_step_model import find_run_step
from skiller.domain.step.runner_port import RunnerPort
from skiller.domain.step.step_type import StepType

_PACKAGED_INSTRUCTION_PATTERN = re.compile(r"^[a-z][a-z0-9_-]*$")


@dataclass(frozen=True)
class RenderCurrentStepResult:
    status: CurrentStepStatus
    current_step: CurrentStep | None = None


class RenderCurrentStepUseCase:
    def __init__(self, store: RunStorePort, skill_runner: RunnerPort) -> None:
        self.store = store
        self.skill_runner = skill_runner

    def execute(self, run_id: str) -> RenderCurrentStepResult:
        run = self.store.get_run(run_id)
        if run is None:
            return RenderCurrentStepResult(status=CurrentStepStatus.RUN_NOT_FOUND)

        if run.status == RunStatus.CANCELLED.value:
            return RenderCurrentStepResult(status=CurrentStepStatus.CANCELLED)

        if run.status == RunStatus.WAITING.value:
            return RenderCurrentStepResult(status=CurrentStepStatus.WAITING)

        if run.status == RunStatus.SUCCEEDED.value:
            return RenderCurrentStepResult(status=CurrentStepStatus.SUCCEEDED)

        if run.status == RunStatus.FAILED.value:
            return RenderCurrentStepResult(status=CurrentStepStatus.FAILED)

        skill = run.snapshot
        if not isinstance(skill, dict):
            return RenderCurrentStepResult(status=CurrentStepStatus.INVALID_SKILL)

        raw_steps = skill.get("steps", [])

        current = run.current
        if current is None:
            return RenderCurrentStepResult(status=CurrentStepStatus.INVALID_SKILL)

        try:
            step_index, parsed_step = find_run_step(raw_steps, current)
        except ValueError:
            return RenderCurrentStepResult(status=CurrentStepStatus.INVALID_SKILL)

        step = self.skill_runner.render(
            parsed_step.body,
            run.context.to_dict(),
            flow=run,
        )
        if not isinstance(step, dict):
            return RenderCurrentStepResult(status=CurrentStepStatus.INVALID_STEP)
        if parsed_step.step_type == StepType.AGENT:
            step = self._resolve_agent_system_file(
                skill_source=run.source,
                skill_ref=run.ref,
                step=step,
            )
            step = self._resolve_agent_instructions(
                skill_source=run.source,
                skill_ref=run.ref,
                step=step,
            )

        return RenderCurrentStepResult(
            status=CurrentStepStatus.READY,
            current_step=CurrentStep(
                run_id=run_id,
                step_index=step_index,
                step_id=parsed_step.step_id,
                step_type=parsed_step.step_type,
                step=step,
                context=run.context,
                run_created_at=run.created_at,
            ),
        )

    def _resolve_agent_system_file(
        self,
        *,
        skill_source: str,
        skill_ref: str,
        step: dict[str, Any],
    ) -> dict[str, Any]:
        raw_system = step.get("system")
        if not isinstance(raw_system, dict) or "file" not in raw_system:
            return step

        file_ref = raw_system.get("file")
        if not isinstance(file_ref, str) or not file_ref.strip():
            raise ValueError("Agent step system.file must be a non-empty string")

        resolved_step = dict(step)
        resolved_step["system"] = self.skill_runner.read_file(
            skill_source,
            skill_ref,
            file_ref,
        )
        return resolved_step

    def _resolve_agent_instructions(
        self,
        *,
        skill_source: str,
        skill_ref: str,
        step: dict[str, Any],
    ) -> dict[str, Any]:
        raw_instructions = step.get("instructions")
        if raw_instructions is None:
            return step
        if not isinstance(raw_instructions, list):
            raise ValueError("Agent step instructions must be a list")

        resolved_instructions: list[str] = []
        for instruction_ref in raw_instructions:
            if not isinstance(instruction_ref, str) or not instruction_ref.strip():
                raise ValueError("Agent step instructions must contain non-empty strings")
            resolved_instructions.append(
                self._read_instruction(
                    skill_source=skill_source,
                    skill_ref=skill_ref,
                    instruction_ref=instruction_ref.strip(),
                )
            )

        resolved_step = dict(step)
        resolved_step["instructions"] = resolved_instructions
        return resolved_step

    def _read_instruction(
        self,
        *,
        skill_source: str,
        skill_ref: str,
        instruction_ref: str,
    ) -> str:
        if instruction_ref.startswith("./") or instruction_ref.startswith("../"):
            return self.skill_runner.read_file(skill_source, skill_ref, instruction_ref)
        if not _PACKAGED_INSTRUCTION_PATTERN.fullmatch(instruction_ref):
            raise ValueError("Agent step instruction package names must be slugs")

        instruction_path = _find_packaged_instruction_dir() / f"{instruction_ref}.md"
        if not instruction_path.is_file():
            raise ValueError(f"Agent step instruction '{instruction_ref}' was not found")
        return instruction_path.read_text(encoding="utf-8")


def _find_packaged_instruction_dir() -> Path:
    for instructions_dir in _packaged_instruction_dir_candidates(Path(__file__).resolve()):
        if instructions_dir.is_dir():
            return instructions_dir

    raise ValueError("Packaged instruction directory was not found")


def _packaged_instruction_dir_candidates(module_path: Path) -> tuple[Path, ...]:
    return tuple(parent / "apps" / "instructions" for parent in module_path.parents)
