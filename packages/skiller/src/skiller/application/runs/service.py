from skiller.application.runs.executor import RunExecutor
from skiller.application.runs.models import (
    ResumeRunApplicationResult,
    RunResult,
    WorkerStartResult,
    WorkerStartStatus,
)
from skiller.application.use_cases.flow.flow_checker import (
    FlowCheckerUseCase,
    FlowCheckStatus,
)
from skiller.application.use_cases.flow.flow_readiness_checker import (
    FlowReadinessCheckerUseCase,
    FlowReadinessCheckStatus,
)
from skiller.application.use_cases.query.get_run import GetRunUseCase
from skiller.application.use_cases.run.append_runtime_event import AppendRuntimeEventUseCase
from skiller.application.use_cases.run.bootstrap_runtime import BootstrapRuntimeUseCase
from skiller.application.use_cases.run.create_run import CreateRunInput, CreateRunUseCase
from skiller.application.use_cases.run.delete_run import DeleteRunResult, DeleteRunUseCase
from skiller.application.use_cases.run.fail_run import FailRunUseCase
from skiller.application.use_cases.run.get_start_step import GetStartStepUseCase
from skiller.application.use_cases.run.mark_notify_action_done import (
    MarkNotifyActionDoneInput,
    MarkNotifyActionDoneResult,
    MarkNotifyActionDoneUseCase,
)
from skiller.application.use_cases.run.resume_run import ResumeRunStatus, ResumeRunUseCase
from skiller.domain.event.event_model import (
    RunCreatedPayload,
    RunFinishedPayload,
    RunResumedPayload,
    RuntimeEventType,
)
from skiller.domain.run.run_model import Run, RunStatus


class RunApplicationService:
    def __init__(
        self,
        bootstrap_runtime_use_case: BootstrapRuntimeUseCase,
        append_runtime_event_use_case: AppendRuntimeEventUseCase,
        create_run_use_case: CreateRunUseCase,
        delete_run_use_case: DeleteRunUseCase,
        fail_run_use_case: FailRunUseCase,
        get_start_step_use_case: GetStartStepUseCase,
        flow_checker_use_case: FlowCheckerUseCase,
        flow_readiness_checker_use_case: FlowReadinessCheckerUseCase,
        resume_run_use_case: ResumeRunUseCase,
        mark_notify_action_done_use_case: MarkNotifyActionDoneUseCase,
        get_run_use_case: GetRunUseCase,
        run_executor: RunExecutor,
    ) -> None:
        self.bootstrap_runtime_use_case = bootstrap_runtime_use_case
        self.append_runtime_event_use_case = append_runtime_event_use_case
        self.create_run_use_case = create_run_use_case
        self.delete_run_use_case = delete_run_use_case
        self.fail_run_use_case = fail_run_use_case
        self.get_start_step_use_case = get_start_step_use_case
        self.flow_checker_use_case = flow_checker_use_case
        self.flow_readiness_checker_use_case = flow_readiness_checker_use_case
        self.resume_run_use_case = resume_run_use_case
        self.mark_notify_action_done_use_case = mark_notify_action_done_use_case
        self.get_run_use_case = get_run_use_case
        self.run_executor = run_executor

    def initialize(self) -> None:
        self.bootstrap_runtime_use_case.initialize()

    def run(self, request: CreateRunInput) -> RunResult:
        created = self.create_run(request)
        self.prepare_run(created.run_id)
        self.dispatch_run(created.run_id)
        return self.get_run_result(created.run_id)

    def start_worker(self, run_id: str) -> WorkerStartResult:
        run = self._get_run_or_raise(run_id)
        if run.status != RunStatus.CREATED.value:
            raise ValueError(f"Run '{run_id}' must be CREATED for worker start")

        self.prepare_run(run_id)
        result = self.get_run_result(run_id)
        start_status = WorkerStartStatus.FAILED
        if result.status != RunStatus.FAILED:
            start_status = WorkerStartStatus.PREPARED
        return WorkerStartResult(
            run_id=run_id,
            start_status=start_status,
            status=result.status,
        )

    def run_worker(self, run_id: str) -> RunResult:
        run = self._get_run_or_raise(run_id)
        blocked_statuses = {
            RunStatus.WAITING.value,
            RunStatus.SUCCEEDED.value,
            RunStatus.FAILED.value,
            RunStatus.CANCELLED.value,
        }
        if run.status in blocked_statuses:
            raise ValueError(f"Run '{run_id}' cannot be executed from status '{run.status}'")
        if run.current is None:
            raise ValueError(f"Run '{run_id}' must be prepared before worker run")

        self.dispatch_run(run_id)
        return self.get_run_result(run_id)

    def create_run(self, request: CreateRunInput) -> RunResult:
        check_result = self.flow_checker_use_case.execute(
            request.skill_ref,
            flow_source=request.skill_source,
        )
        if check_result.status == FlowCheckStatus.INVALID:
            messages = [item.message for item in check_result.errors]
            raise ValueError("\n".join(messages))
        readiness_check_result = self.flow_readiness_checker_use_case.execute(
            request.skill_ref,
            flow_source=request.skill_source,
        )
        if readiness_check_result.status == FlowReadinessCheckStatus.INVALID:
            messages = [item.message for item in readiness_check_result.errors]
            raise ValueError("\n".join(messages))
        run_id = self.create_run_use_case.execute(request)
        self.append_runtime_event_use_case.execute(
            run_id,
            event_type=RuntimeEventType.RUN_CREATE,
            payload=RunCreatedPayload(ref=request.skill_ref, source=request.skill_source),
        )
        return RunResult(run_id=run_id, status=RunStatus.CREATED)

    def prepare_run(self, run_id: str) -> None:
        try:
            self.get_start_step_use_case.execute(run_id)
        except Exception as exc:  # noqa: BLE001
            error = str(exc)
            self.fail_run_use_case.execute(run_id, error=error)
            self.append_runtime_event_use_case.execute(
                run_id,
                event_type=RuntimeEventType.RUN_FINISHED,
                payload=RunFinishedPayload(status=RunStatus.FAILED.value, error=error),
            )

    def dispatch_run(self, run_id: str) -> None:
        self.run_executor.run(run_id)

    def get_run_result(self, run_id: str) -> RunResult:
        run = self.get_run_use_case.execute(run_id)
        status = RunStatus.FAILED
        if run is not None:
            status = RunStatus(run.status)
        return RunResult(run_id=run_id, status=status)

    def delete_run(self, run_id: str) -> DeleteRunResult:
        return self.delete_run_use_case.execute(run_id)

    def resume_run(self, run_id: str) -> ResumeRunApplicationResult:
        result = self.resume_run_use_case.execute(run_id, source="manual")
        if result.status == ResumeRunStatus.RESUMED:
            self.append_runtime_event_use_case.execute(
                run_id,
                event_type=RuntimeEventType.RUN_RESUME,
                payload=RunResumedPayload(source="manual"),
            )
            self.run_executor.run(run_id)
        status_payload = self.get_run_result(run_id)
        return ResumeRunApplicationResult(
            run_id=run_id,
            resume_status=result.status,
            status=status_payload.status,
        )

    def mark_notify_action_done(
        self,
        request: MarkNotifyActionDoneInput,
    ) -> MarkNotifyActionDoneResult:
        return self.mark_notify_action_done_use_case.execute(request)

    def _get_run_or_raise(self, run_id: str) -> Run:
        run = self.get_run_use_case.execute(run_id)
        if run is None:
            raise ValueError(f"Run '{run_id}' not found")
        return run
