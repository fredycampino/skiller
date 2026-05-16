from skiller.domain.run.run_store_port import RunStorePort
from skiller.domain.step.run_step_model import find_run_step


class GetStartStepUseCase:
    def __init__(self, store: RunStorePort) -> None:
        self.store = store

    def execute(self, run_id: str) -> str:
        run = self.store.get_run(run_id)
        if run is None:
            raise ValueError(f"Run '{run_id}' not found")

        snapshot = run.snapshot
        if not isinstance(snapshot, dict):
            raise ValueError(f"Run '{run_id}' has invalid snapshot")

        raw_steps = snapshot.get("steps", [])

        start_step_id = str(snapshot.get("start", "")).strip()
        if not start_step_id:
            raise ValueError(f"Run '{run_id}' requires a non-empty root 'start'")

        try:
            find_run_step(raw_steps, start_step_id)
        except ValueError as exc:
            raise ValueError(
                f"Run '{run_id}' requires exactly one step with id '{start_step_id}'"
            ) from exc

        self.store.update_run(run_id, current=start_step_id)
        return start_step_id
