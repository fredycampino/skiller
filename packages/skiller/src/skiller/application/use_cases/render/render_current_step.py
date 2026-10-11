from dataclasses import dataclass
from pathlib import Path
from typing import Any

from skiller.domain.agent.instruction_reference import parse_instruction_references
from skiller.domain.run.run_model import RunStatus
from skiller.domain.run.run_store_port import RunStorePort
from skiller.domain.step.current_step_model import CurrentStep, CurrentStepStatus
from skiller.domain.step.run_step_model import find_run_step
from skiller.domain.step.runner_port import RunnerPort
from skiller.domain.step.step_type import StepType


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

        render_body = dict(parsed_step.body)
        if parsed_step.step_type == StepType.AGENT:
            render_body.pop("config", None)
            render_body.pop("instructions", None)
            if isinstance(parsed_step.body.get("system"), dict):
                render_body.pop("system", None)
        step = self.skill_runner.render(
            render_body,
            run.context.to_dict(),
            flow=run,
        )
        if not isinstance(step, dict):
            return RenderCurrentStepResult(status=CurrentStepStatus.INVALID_STEP)
        if parsed_step.step_type == StepType.AGENT:
            if "instructions" in parsed_step.body:
                step["instructions"] = parsed_step.body["instructions"]
            if "config" in parsed_step.body:
                step["config"] = parsed_step.body["config"]
            if isinstance(parsed_step.body.get("system"), dict):
                step["system"] = parsed_step.body["system"]
            step = self._resolve_agent_system_file(
                flow_path=run.flow_path,
                step=step,
            )
            step = self._resolve_agent_instructions(
                flow_path=run.flow_path,
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
        flow_path: Path,
        step: dict[str, Any],
    ) -> dict[str, Any]:
        raw_system = step.get("system")
        if not isinstance(raw_system, dict):
            return step

        if set(raw_system) != {"file"}:
            raise ValueError("Agent step system must contain exactly 'file'")
        file_ref = raw_system.get("file")
        if not isinstance(file_ref, str) or not file_ref.strip():
            raise ValueError("Agent step system.file must be a non-empty string")

        resolved_step = dict(step)
        resolved_step["system"] = self.skill_runner.read_system_file(
            flow_path,
            file_ref,
        )
        return resolved_step

    def _resolve_agent_instructions(
        self,
        *,
        flow_path: Path,
        step: dict[str, Any],
    ) -> dict[str, Any]:
        if "instructions" not in step:
            return step
        references = parse_instruction_references(step["instructions"])
        resolved_instructions = [
            self.skill_runner.read_instruction(flow_path, reference)
            for reference in references
        ]
        resolved_step = dict(step)
        resolved_step["instructions"] = resolved_instructions
        return resolved_step
