from skiller.application.ports.state_store_port import StateStorePort


class GetStartStepUseCase:
    def __init__(self, store: StateStorePort) -> None:
        self.store = store

    def execute(self, run_id: str) -> str:
        run = self.store.get_run(run_id)
        if run is None:
            raise ValueError(f"Run '{run_id}' not found")

        skill = run.skill_snapshot
        if not isinstance(skill, dict):
            raise ValueError(f"Run '{run_id}' has invalid skill snapshot")

        raw_steps = skill.get("steps", [])
        if not isinstance(raw_steps, list):
            raise ValueError(f"Run '{run_id}' has invalid steps list")

        start_matches: list[str] = []
        for raw_step in raw_steps:
            if not isinstance(raw_step, dict):
                raise ValueError(f"Run '{run_id}' has invalid step entry")
            step_id = str(raw_step.get("id", "")).strip()
            if step_id == "start":
                start_matches.append(step_id)

        if not start_matches:
            raise ValueError(f"Run '{run_id}' requires exactly one step with id 'start'")
        if len(start_matches) > 1:
            raise ValueError(f"Run '{run_id}' requires exactly one step with id 'start'")

        self.store.update_run(run_id, current="start")
        return "start"
