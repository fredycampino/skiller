from skiller.application.ports.run_store_port import RunStorePort
from skiller.application.tools.notify import NotifyTool, NotifyToolAdapter
from skiller.application.use_cases.render.render_current_step import CurrentStep
from skiller.application.use_cases.shared.step_execution_result import (
    StepAdvance,
    StepExecutionStatus,
)
from skiller.domain.run.run_model import RunStatus
from skiller.domain.step.step_execution_model import NotifyOutput, StepExecution


class ExecuteNotifyStepUseCase:
    def __init__(self, store: RunStorePort) -> None:
        self.store = store
        self.notify_tool_adapter = NotifyToolAdapter()
        self.notify_tool = NotifyTool()

    def execute(self, next_step: CurrentStep) -> StepAdvance:
        step_id = next_step.step_id
        step = next_step.step
        context = next_step.context

        notify_request = self.notify_tool_adapter.build_request(
            step_id=step_id,
            value={"message": step.get("message")},
        )
        notify_result = self.notify_tool.execute(notify_request)
        message = str(notify_result.data.get("message", ""))
        execution = StepExecution(
            step_type=next_step.step_type,
            input={"message": notify_request.message},
            evaluation={},
            output=NotifyOutput(text=notify_result.text or message, message=message),
        )
        context.step_executions[step_id] = execution

        raw_next = step.get("next")
        if raw_next is None:
            self.store.update_run(
                next_step.run_id,
                status=RunStatus.RUNNING,
                context=context,
            )
            return StepAdvance(
                status=StepExecutionStatus.COMPLETED,
                execution=execution,
            )

        next_step_id = str(raw_next).strip()
        if not next_step_id:
            raise ValueError(f"Step '{step_id}' requires non-empty next")

        self.store.update_run(
            next_step.run_id,
            status=RunStatus.RUNNING,
            current=next_step_id,
            context=context,
        )
        return StepAdvance(
            status=StepExecutionStatus.NEXT,
            next_step_id=next_step_id,
            execution=execution,
        )
