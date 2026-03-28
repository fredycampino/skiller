from skiller.application.ports.state_store_port import StateStorePort
from skiller.application.use_cases.render_current_step import CurrentStep
from skiller.application.use_cases.step_execution_result import (
    StepExecutionResult,
    StepExecutionStatus,
    WaitWebhookResult,
)
from skiller.domain.run_model import RunStatus


class ExecuteWaitWebhookStepUseCase:
    def __init__(self, store: StateStorePort) -> None:
        self.store = store

    def execute(self, current_step: CurrentStep) -> StepExecutionResult:
        step = current_step.step
        step_id = current_step.step_id
        webhook = str(step.get("webhook", "")).strip()
        key = str(step.get("key", "")).strip()

        if not webhook:
            raise ValueError(f"Step '{step_id}' requires webhook")
        if not key:
            raise ValueError(f"Step '{step_id}' requires key")

        active_wait = self.store.get_active_wait(current_step.run_id, step_id)
        since_created_at = str(active_wait["created_at"]) if active_wait is not None else None
        webhook_event = self.store.get_latest_webhook_event(
            webhook, key, since_created_at=since_created_at
        )

        if webhook_event is not None:
            current_step.context.results[step_id] = {
                "ok": True,
                "webhook": webhook,
                "key": key,
                "payload": webhook_event["payload"],
            }
            if active_wait is not None:
                self.store.resolve_wait(str(active_wait["id"]))

            raw_next = step.get("next")
            if raw_next is None:
                self.store.update_run(
                    current_step.run_id,
                    status=RunStatus.RUNNING,
                    context=current_step.context,
                )
                return StepExecutionResult(
                    status=StepExecutionStatus.COMPLETED,
                    result=WaitWebhookResult(
                        webhook=webhook,
                        key=key,
                        payload=webhook_event["payload"],
                    ),
                )

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
                result=WaitWebhookResult(
                    webhook=webhook,
                    key=key,
                    payload=webhook_event["payload"],
                ),
            )

        if active_wait is None:
            self.store.create_wait(
                current_step.run_id,
                webhook,
                key,
                step_id=step_id,
            )
        self.store.update_run(
            current_step.run_id,
            status=RunStatus.WAITING,
            current=step_id,
            context=current_step.context,
        )
        return StepExecutionResult(
            status=StepExecutionStatus.WAITING,
            result=WaitWebhookResult(webhook=webhook, key=key),
        )
