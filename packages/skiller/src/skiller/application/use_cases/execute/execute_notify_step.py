from skiller.application.tools.notify import NotifyTool
from skiller.domain.run.run_model import RunStatus
from skiller.domain.run.run_store_port import RunStorePort
from skiller.domain.step.current_step_model import CurrentStep
from skiller.domain.step.step_execution_model import (
    NotifyActionStatus,
    NotifyActionType,
    NotifyOpenUrlAction,
    NotifyOutput,
    NotifyOutputFormat,
    StepExecution,
)
from skiller.domain.step.step_execution_result_model import (
    StepAdvance,
    StepExecutionStatus,
)
from skiller.domain.tool.tool_contract import ToolInput


class ExecuteNotifyStepUseCase:
    def __init__(self, store: RunStorePort) -> None:
        self.store = store
        self.notify_tool = NotifyTool()

    def execute(self, next_step: CurrentStep) -> StepAdvance:
        step_id = next_step.step_id
        step = next_step.step
        context = next_step.context

        notify_request_result = self.notify_tool.request(
            ToolInput(
                run_id=next_step.run_id,
                step_id=step_id,
                tool_call_id=step_id,
                args={"message": step.get("message")},
            )
        )
        if not notify_request_result.ok:
            raise ValueError(
                notify_request_result.error or f"Notify step '{step_id}' request failed"
            )
        if notify_request_result.request is None:
            raise ValueError(f"Notify step '{step_id}' request returned no request")
        notify_request = notify_request_result.request
        notify_result = self.notify_tool.run(
            config=None,
            request=notify_request,
        )
        message = str(notify_result.data.get("message", ""))
        raw_format = step.get("format", NotifyOutputFormat.SIMPLE.value)
        try:
            output_format = NotifyOutputFormat(str(raw_format))
        except ValueError as exc:
            raise ValueError(
                f"Notify step '{step_id}' has unsupported format '{raw_format}'"
            ) from exc
        action = _build_notify_action(step_id, step)
        action_type = NotifyActionType.OPEN_URL if action is not None else None
        execution = StepExecution(
            step_type=next_step.step_type,
            input={"message": notify_request.message},
            evaluation={},
            output=NotifyOutput(
                text=notify_result.text or message,
                message=message,
                format=output_format,
                action_type=action_type,
                action=action,
            ),
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


def _build_notify_action(
    step_id: str,
    step: dict[str, object],
) -> NotifyOpenUrlAction | None:
    raw_action = step.get("action")
    if raw_action is None:
        return None

    if not isinstance(raw_action, dict):
        raise ValueError(f"Notify step '{step_id}' action must be an object")

    action_type = str(raw_action.get("type", "")).strip()
    if action_type != NotifyActionType.OPEN_URL.value:
        raise ValueError(
            f"Notify step '{step_id}' action type must be '{NotifyActionType.OPEN_URL.value}'"
        )

    label = str(raw_action.get("label", "")).strip()
    if not label:
        raise ValueError(f"Notify step '{step_id}' action requires non-empty label")

    url = str(raw_action.get("url", "")).strip()
    if not _is_http_url(url):
        raise ValueError(f"Notify step '{step_id}' action requires http(s) url")

    raw_auto_open = raw_action.get("auto_open", False)
    if not isinstance(raw_auto_open, bool):
        raise ValueError(f"Notify step '{step_id}' action auto_open must be boolean")

    return NotifyOpenUrlAction(
        label=label,
        url=url,
        status=NotifyActionStatus.PENDING,
        auto_open=raw_auto_open,
    )


def _is_http_url(value: str) -> bool:
    return value.startswith(("http://", "https://"))
