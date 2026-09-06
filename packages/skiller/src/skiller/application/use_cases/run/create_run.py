import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from skiller.domain.run.run_context_model import RunContext
from skiller.domain.run.run_store_port import RunStorePort
from skiller.domain.step.run_step_model import validate_skill_snapshot
from skiller.domain.step.runner_port import RunnerPort


@dataclass(frozen=True)
class CreateRunInput:
    flow_path: Path
    inputs: dict[str, Any]


class CreateRunUseCase:
    def __init__(self, store: RunStorePort, skill_runner: RunnerPort) -> None:
        self.store = store
        self.skill_runner = skill_runner

    def execute(self, request: CreateRunInput) -> str:
        run_id = str(uuid.uuid4())
        raw_skill = self.skill_runner.load(request.flow_path)
        try:
            snapshot = validate_skill_snapshot(raw_skill)
        except ValueError as exc:
            raise ValueError(f"Invalid flow format for '{request.flow_path}'. {exc}") from exc
        context = RunContext(inputs=request.inputs, step_executions={})
        return self.store.create_run(
            request.flow_path,
            snapshot,
            context,
            run_id=run_id,
        )
