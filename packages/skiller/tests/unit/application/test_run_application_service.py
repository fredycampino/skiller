from types import SimpleNamespace

import pytest

from skiller.application.runs.service import RunApplicationService
from skiller.application.use_cases.flow.flow_checker import (
    FlowCheckError,
    FlowCheckResult,
    FlowCheckStatus,
)
from skiller.application.use_cases.flow.flow_readiness_checker import (
    FlowReadinessCheckError,
    FlowReadinessCheckResult,
    FlowReadinessCheckStatus,
)
from skiller.application.use_cases.run.bootstrap_runtime import BootstrapRuntimeUseCase
from skiller.application.use_cases.run.create_run import CreateRunInput
from skiller.application.use_cases.run.resume_run import ResumeRunResult, ResumeRunStatus
from skiller.domain.event.event_model import (
    RuntimeEventPayload,
    RuntimeEventType,
    runtime_event_payload_to_dict,
)

pytestmark = pytest.mark.unit


class _FakeCreateRunUseCase:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def execute(self, request: CreateRunInput) -> str:
        self.calls.append(
            {
                "skill_ref": request.skill_ref,
                "inputs": request.inputs,
                "skill_source": request.skill_source,
            }
        )
        return "run-1"


class _FakeAppendRuntimeEventUseCase:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def execute(
        self,
        run_id: str,
        *,
        event_type: RuntimeEventType,
        payload: RuntimeEventPayload | dict[str, object],
        step_id: str | None = None,
        step_type: str | None = None,
        agent_sequence: int | None = None,
    ) -> None:
        self.calls.append(
            {
                "run_id": run_id,
                "event_type": event_type,
                "payload": runtime_event_payload_to_dict(payload),
                "step_id": step_id,
                "step_type": step_type,
                "agent_sequence": agent_sequence,
            }
        )


class _FakeFlowCheckerUseCase:
    def __init__(self, result: FlowCheckResult | None = None) -> None:
        self.result = result or FlowCheckResult(status=FlowCheckStatus.VALID, errors=[])
        self.calls: list[dict[str, object]] = []

    def execute(self, flow_ref: str, *, flow_source: str) -> FlowCheckResult:
        self.calls.append({"flow_ref": flow_ref, "flow_source": flow_source})
        return self.result


class _FakeFlowReadinessCheckerUseCase:
    def __init__(self, result: FlowReadinessCheckResult | None = None) -> None:
        self.result = result or FlowReadinessCheckResult(
            status=FlowReadinessCheckStatus.VALID,
            errors=[],
        )
        self.calls: list[dict[str, object]] = []

    def execute(self, flow_ref: str, *, flow_source: str) -> FlowReadinessCheckResult:
        self.calls.append({"flow_ref": flow_ref, "flow_source": flow_source})
        return self.result


class _FakeFailRunUseCase:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def execute(self, run_id: str, *, error: str) -> None:
        self.calls.append({"run_id": run_id, "error": error})


class _FakeGetStartStepUseCase:
    def __init__(self, get_run_use_case: "_FakeGetRunUseCase | None" = None) -> None:
        self.get_run_use_case = get_run_use_case
        self.calls: list[str] = []

    def execute(self, run_id: str) -> str:
        self.calls.append(run_id)
        if self.get_run_use_case is not None:
            self.get_run_use_case.current = "start"
        return "start"


class _FakeResumeRunUseCase:
    def __init__(self, *, status: ResumeRunStatus = ResumeRunStatus.NOT_WAITING) -> None:
        self.status = status
        self.calls: list[dict[str, str]] = []

    def execute(self, run_id: str, *, source: str = "manual") -> ResumeRunResult:
        self.calls.append({"run_id": run_id, "source": source})
        return ResumeRunResult(status=self.status)


class _FakeGetRunUseCase:
    def __init__(self, status: str = "CREATED", current: str | None = None) -> None:
        self.status = status
        self.current = current
        self.calls: list[str] = []

    def execute(self, run_id: str):  # noqa: ANN201
        self.calls.append(run_id)
        return SimpleNamespace(status=self.status, current=self.current)


class _FakeRunExecutor:
    def __init__(
        self,
        get_run_use_case: _FakeGetRunUseCase | None = None,
        *,
        final_status: str = "SUCCEEDED",
    ) -> None:
        self.get_run_use_case = get_run_use_case
        self.final_status = final_status
        self.calls: list[str] = []

    def run(self, run_id: str):  # noqa: ANN201
        self.calls.append(run_id)
        if self.get_run_use_case is not None:
            self.get_run_use_case.status = self.final_status
        return SimpleNamespace(run_id=run_id, status=self.final_status, error=None)


def _build_service(
    *,
    get_run_use_case: _FakeGetRunUseCase | None = None,
    flow_checker_use_case: _FakeFlowCheckerUseCase | None = None,
    flow_readiness_checker_use_case: _FakeFlowReadinessCheckerUseCase | None = None,
    worker_final_status: str = "SUCCEEDED",
) -> tuple[
    RunApplicationService,
    _FakeAppendRuntimeEventUseCase,
    _FakeCreateRunUseCase,
    _FakeGetStartStepUseCase,
    _FakeRunExecutor,
    _FakeFlowCheckerUseCase,
    _FakeFlowReadinessCheckerUseCase,
]:
    append_runtime_event_use_case = _FakeAppendRuntimeEventUseCase()
    create_run_use_case = _FakeCreateRunUseCase()
    final_flow_checker_use_case = flow_checker_use_case or _FakeFlowCheckerUseCase()
    final_flow_readiness_checker_use_case = (
        flow_readiness_checker_use_case or _FakeFlowReadinessCheckerUseCase()
    )
    final_get_run_use_case = get_run_use_case or _FakeGetRunUseCase()
    get_start_step_use_case = _FakeGetStartStepUseCase(get_run_use_case=final_get_run_use_case)
    run_executor = _FakeRunExecutor(
        get_run_use_case=final_get_run_use_case,
        final_status=worker_final_status,
    )
    service = RunApplicationService(
        bootstrap_runtime_use_case=BootstrapRuntimeUseCase(
            store=SimpleNamespace(init_db=lambda: None),
        ),
        append_runtime_event_use_case=append_runtime_event_use_case,
        create_run_use_case=create_run_use_case,
        delete_run_use_case=SimpleNamespace(execute=lambda run_id: None),
        fail_run_use_case=_FakeFailRunUseCase(),
        get_start_step_use_case=get_start_step_use_case,
        flow_checker_use_case=final_flow_checker_use_case,
        flow_readiness_checker_use_case=final_flow_readiness_checker_use_case,
        resume_run_use_case=_FakeResumeRunUseCase(),
        mark_notify_action_done_use_case=SimpleNamespace(
            execute=lambda request: None,
        ),
        get_run_use_case=final_get_run_use_case,
        run_executor=run_executor,
    )
    return (
        service,
        append_runtime_event_use_case,
        create_run_use_case,
        get_start_step_use_case,
        run_executor,
        final_flow_checker_use_case,
        final_flow_readiness_checker_use_case,
    )


def test_create_run_only_creates_run() -> None:
    (
        service,
        append_runtime_event_use_case,
        create_run_use_case,
        get_start_step_use_case,
        run_executor,
        flow_checker_use_case,
        flow_readiness_checker_use_case,
    ) = _build_service()

    result = service.create_run(
        CreateRunInput(
            skill_ref="notify_test",
            inputs={"message": "ok"},
            skill_source="internal",
        )
    )

    assert result.run_id == "run-1"
    assert result.status.value == "CREATED"
    assert create_run_use_case.calls == [
        {
            "skill_ref": "notify_test",
            "inputs": {"message": "ok"},
            "skill_source": "internal",
        }
    ]
    assert get_start_step_use_case.calls == []
    assert run_executor.calls == []

    assert flow_checker_use_case.calls == [
        {"flow_ref": "notify_test", "flow_source": "internal"}
    ]
    assert flow_readiness_checker_use_case.calls == [
        {"flow_ref": "notify_test", "flow_source": "internal"}
    ]
    assert append_runtime_event_use_case.calls == [
        {
            "run_id": "run-1",
            "event_type": RuntimeEventType.RUN_CREATE,
            "step_id": None,
            "step_type": None,
            "agent_sequence": None,
            "payload": {"ref": "notify_test", "source": "internal"},
        }
    ]


def test_run_prepares_dispatches_and_reads_final_status() -> None:
    get_run_use_case = _FakeGetRunUseCase(status="WAITING")
    (
        service,
        _append_runtime_event_use_case,
        _create_run_use_case,
        get_start_step_use_case,
        run_executor,
        _flow_checker_use_case,
        _flow_readiness_checker_use_case,
    ) = _build_service(
        get_run_use_case=get_run_use_case,
        worker_final_status="WAITING",
    )

    result = service.run(
        CreateRunInput(
            skill_ref="notify_test",
            inputs={},
            skill_source="internal",
        )
    )

    assert result.run_id == "run-1"
    assert result.status.value == "WAITING"
    assert get_start_step_use_case.calls == ["run-1"]
    assert run_executor.calls == ["run-1"]
    assert get_run_use_case.calls == ["run-1"]


def test_start_worker_prepares_created_run() -> None:
    (
        service,
        _append_runtime_event_use_case,
        _create_run_use_case,
        get_start_step_use_case,
        run_executor,
        _flow_checker_use_case,
        _flow_readiness_checker_use_case,
    ) = _build_service()

    result = service.start_worker("run-1")

    assert result.run_id == "run-1"
    assert result.start_status.value == "PREPARED"
    assert result.status.value == "CREATED"
    assert get_start_step_use_case.calls == ["run-1"]
    assert run_executor.calls == []


def test_run_worker_dispatches_prepared_run() -> None:
    get_run_use_case = _FakeGetRunUseCase(status="RUNNING", current="start")
    (
        service,
        _append_runtime_event_use_case,
        _create_run_use_case,
        _get_start_step_use_case,
        run_executor,
        _flow_checker_use_case,
        _flow_readiness_checker_use_case,
    ) = _build_service(
        get_run_use_case=get_run_use_case,
    )
    service.prepare_run("run-1")

    result = service.run_worker("run-1")

    assert result.run_id == "run-1"
    assert result.status.value == "SUCCEEDED"
    assert run_executor.calls == ["run-1"]


def test_resume_run_emits_runtime_event_and_dispatches_worker() -> None:
    get_run_use_case = _FakeGetRunUseCase(status="WAITING")
    append_runtime_event_use_case = _FakeAppendRuntimeEventUseCase()
    resume_run_use_case = _FakeResumeRunUseCase(status=ResumeRunStatus.RESUMED)
    run_executor = _FakeRunExecutor(
        get_run_use_case=get_run_use_case,
        final_status="WAITING",
    )

    service = RunApplicationService(
        bootstrap_runtime_use_case=BootstrapRuntimeUseCase(
            store=SimpleNamespace(init_db=lambda: None),
        ),
        append_runtime_event_use_case=append_runtime_event_use_case,
        create_run_use_case=_FakeCreateRunUseCase(),
        delete_run_use_case=SimpleNamespace(execute=lambda run_id: None),
        fail_run_use_case=_FakeFailRunUseCase(),
        get_start_step_use_case=_FakeGetStartStepUseCase(
            get_run_use_case=get_run_use_case
        ),
        flow_checker_use_case=_FakeFlowCheckerUseCase(),
        flow_readiness_checker_use_case=_FakeFlowReadinessCheckerUseCase(),
        resume_run_use_case=resume_run_use_case,
        mark_notify_action_done_use_case=SimpleNamespace(
            execute=lambda request: None,
        ),
        get_run_use_case=get_run_use_case,
        run_executor=run_executor,
    )

    result = service.resume_run("run-1")

    assert result.run_id == "run-1"
    assert result.resume_status.value == "RESUMED"
    assert result.status.value == "WAITING"
    assert resume_run_use_case.calls == [{"run_id": "run-1", "source": "manual"}]
    assert append_runtime_event_use_case.calls == [
        {
            "run_id": "run-1",
            "event_type": RuntimeEventType.RUN_RESUME,
            "step_id": None,
            "step_type": None,
            "agent_sequence": None,
            "payload": {"source": "manual"},
        }
    ]
    assert run_executor.calls == ["run-1"]


def test_create_run_fails_when_flow_checker_reports_errors() -> None:
    checker = _FakeFlowCheckerUseCase(
        result=FlowCheckResult(
            status=FlowCheckStatus.INVALID,
            errors=[
                FlowCheckError(
                    code="FLOW_NOTIFY_MESSAGE_MISSING",
                    message=(
                        "FLOW_NOTIFY_MESSAGE_MISSING: notify step requires "
                        "message (step=show_message)"
                    ),
                )
            ],
        )
    )
    (
        service,
        append_runtime_event_use_case,
        create_run_use_case,
        _get_start_step_use_case,
        _run_executor,
        _flow_checker_use_case,
        _flow_readiness_checker_use_case,
    ) = _build_service(flow_checker_use_case=checker)

    with pytest.raises(
        ValueError,
        match="FLOW_NOTIFY_MESSAGE_MISSING: notify step requires message",
    ):
        service.create_run(
            CreateRunInput(
                skill_ref="notify_test",
                inputs={},
                skill_source="internal",
            )
        )

    assert checker.calls == [{"flow_ref": "notify_test", "flow_source": "internal"}]
    assert create_run_use_case.calls == []
    assert append_runtime_event_use_case.calls == []


def test_create_run_fails_when_flow_readiness_checker_reports_errors() -> None:
    checker = _FakeFlowReadinessCheckerUseCase(
        result=FlowReadinessCheckResult(
            status=FlowReadinessCheckStatus.INVALID,
            errors=[
                FlowReadinessCheckError(
                    code="FLOW_SERVER_UNAVAILABLE",
                    message=(
                        "FLOW_SERVER_UNAVAILABLE: flow requires local server "
                        "for wait_channel (step=listen_whatsapp)"
                    ),
                )
            ],
        )
    )
    (
        service,
        append_runtime_event_use_case,
        create_run_use_case,
        _get_start_step_use_case,
        _run_executor,
        flow_checker_use_case,
        flow_readiness_checker_use_case,
    ) = _build_service(flow_readiness_checker_use_case=checker)

    with pytest.raises(
        ValueError,
        match="FLOW_SERVER_UNAVAILABLE: flow requires local server",
    ):
        service.create_run(
            CreateRunInput(
                skill_ref="whatsapp_demo",
                inputs={},
                skill_source="internal",
            )
        )

    assert flow_checker_use_case.calls == [
        {"flow_ref": "whatsapp_demo", "flow_source": "internal"}
    ]
    assert flow_readiness_checker_use_case.calls == [
        {"flow_ref": "whatsapp_demo", "flow_source": "internal"}
    ]
    assert create_run_use_case.calls == []
    assert append_runtime_event_use_case.calls == []
