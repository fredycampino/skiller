from skiller.application.ports.state_store_port import StateStorePort
from skiller.application.use_cases.render_current_step import CurrentStep
from skiller.application.use_cases.step_execution_result import (
    StepExecutionResult,
    StepExecutionStatus,
)
from skiller.domain.run_model import RunStatus


class ExecuteWaitInputStepUseCase:
    def __init__(self, store: StateStorePort) -> None:
        self.store = store

    def execute(self, current_step: CurrentStep) -> StepExecutionResult:
        step = current_step.step
        step_id = current_step.step_id
        prompt = str(step.get("prompt", "")).strip()

        if not prompt:
            raise ValueError(f"Step '{step_id}' requires prompt")

        active_wait = self.store.get_active_input_wait(current_step.run_id, step_id)
        since_created_at = str(active_wait["created_at"]) if active_wait is not None else None
        input_event = self.store.get_latest_input_event(
            current_step.run_id,
            step_id,
            since_created_at=since_created_at,
        )

        if input_event is not None:
            payload = input_event.get("payload", {})
            if not isinstance(payload, dict):
                payload = {}

            current_step.context.results[step_id] = {
                "ok": True,
                "prompt": prompt,
                "payload": payload,
            }
            if active_wait is not None:
                self.store.resolve_input_wait(str(active_wait["id"]))

            self.store.append_event(
                "INPUT_RESOLVED",
                {
                    "step": step_id,
                    "wait_id": (active_wait["id"] if active_wait is not None else None),
                    "prompt": prompt,
                    "payload": payload,
                    "input_event_id": input_event["id"],
                },
                run_id=current_step.run_id,
            )

            raw_next = step.get("next")
            if raw_next is None:
                self.store.update_run(
                    current_step.run_id,
                    status=RunStatus.RUNNING,
                    context=current_step.context,
                )
                return StepExecutionResult(status=StepExecutionStatus.COMPLETED)

            next_step_id = str(raw_next).strip()
            if not next_step_id:
                raise ValueError(f"Step '{step_id}' requires non-empty next")

            self.store.update_run(
                current_step.run_id,
                status=RunStatus.RUNNING,
                current=next_step_id,
                context=current_step.context,
            )
            return StepExecutionResult(
                status=StepExecutionStatus.NEXT,
                next_step_id=next_step_id,
            )

        wait_id = (
            str(active_wait["id"])
            if active_wait is not None
            else self.store.create_input_wait(current_step.run_id, step_id)
        )
        self.store.update_run(
            current_step.run_id,
            status=RunStatus.WAITING,
            current=step_id,
            context=current_step.context,
        )
        if active_wait is None:
            self.store.append_event(
                "INPUT_WAITING",
                {"step": step_id, "wait_id": wait_id, "prompt": prompt},
                run_id=current_step.run_id,
            )
        return StepExecutionResult(status=StepExecutionStatus.WAITING)
