from types import SimpleNamespace

import pytest

from skiller.application.runtime_application_service import RuntimeApplicationService
from skiller.application.use_cases.append_runtime_event import RuntimeEventType
from skiller.application.use_cases.bootstrap_runtime import BootstrapRuntimeUseCase
from skiller.application.use_cases.list_webhooks import ListWebhooksResult
from skiller.application.use_cases.remove_webhook import RemoveWebhookStatus
from skiller.application.use_cases.resume_run import ResumeRunResult, ResumeRunStatus

pytestmark = pytest.mark.unit


class _FakeCreateRunUseCase:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def execute(
        self,
        skill_ref: str,
        inputs: dict[str, object],
        *,
        skill_source: str,
    ) -> str:
        self.calls.append(
            {
                "skill_ref": skill_ref,
                "inputs": inputs,
                "skill_source": skill_source,
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
        payload: dict[str, object],
    ) -> None:
        self.calls.append(
            {
                "run_id": run_id,
                "event_type": event_type,
                "payload": payload,
            }
        )


class _FakeFailRunUseCase:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def execute(self, run_id: str, *, error: str) -> None:
        self.calls.append({"run_id": run_id, "error": error})


class _FakeGetStartStepUseCase:
    def __init__(self, run_status_use_case: "_FakeGetRunStatusUseCase | None" = None) -> None:
        self.run_status_use_case = run_status_use_case
        self.calls: list[str] = []

    def execute(self, run_id: str) -> str:
        self.calls.append(run_id)
        if self.run_status_use_case is not None:
            self.run_status_use_case.current = "start"
        return "start"


class _FakeHandleWebhookUseCase:
    def __init__(self, run_ids: list[str] | None = None) -> None:
        self.run_ids = run_ids or []

    def execute(self, webhook: str, key: str, payload: dict[str, object], *, dedup_key: str):  # noqa: ANN001
        return SimpleNamespace(
            accepted=True,
            duplicate=False,
            run_ids=self.run_ids,
        )


class _FakeHandleInputUseCase:
    def __init__(self, run_ids: list[str] | None = None, *, accepted: bool = True) -> None:
        self.run_ids = run_ids or []
        self.accepted = accepted

    def execute(self, run_id: str, *, text: str):  # noqa: ANN201
        _ = (run_id, text)
        return SimpleNamespace(
            accepted=self.accepted,
            run_ids=self.run_ids,
            error=None,
        )


class _FakeRegisterWebhookUseCase:
    def execute(self, webhook: str):  # noqa: ANN201
        return SimpleNamespace(
            webhook=webhook,
            status=SimpleNamespace(value="REGISTERED"),
            secret=None,
            enabled=None,
            error=None,
        )


class _FakeRemoveWebhookUseCase:
    def execute(self, webhook: str):  # noqa: ANN201
        return SimpleNamespace(webhook=webhook, status=RemoveWebhookStatus.REMOVED, error=None)


class _FakeResumeRunUseCase:
    def __init__(self, *, status: ResumeRunStatus = ResumeRunStatus.NOT_WAITING) -> None:
        self.status = status
        self.calls: list[dict[str, str]] = []

    def execute(self, run_id: str, *, source: str = "manual") -> ResumeRunResult:
        self.calls.append({"run_id": run_id, "source": source})
        return ResumeRunResult(status=self.status)


class _FakeGetRunStatusUseCase:
    def __init__(self, status: str = "CREATED", current: str | None = None) -> None:
        self.status = status
        self.current = current
        self.calls: list[str] = []

    def execute(self, run_id: str):  # noqa: ANN201
        self.calls.append(run_id)
        return SimpleNamespace(status=self.status, current=self.current)


class _FakeRunWorkerService:
    def __init__(
        self,
        run_status_use_case: _FakeGetRunStatusUseCase | None = None,
        *,
        final_status: str = "SUCCEEDED",
    ) -> None:
        self.run_status_use_case = run_status_use_case
        self.final_status = final_status
        self.calls: list[str] = []

    def run(self, run_id: str):  # noqa: ANN201
        self.calls.append(run_id)
        if self.run_status_use_case is not None:
            self.run_status_use_case.status = self.final_status
        return SimpleNamespace(run_id=run_id, status=self.final_status, error=None)


class _FakeListWebhooksUseCase:
    def execute(self) -> ListWebhooksResult:
        return ListWebhooksResult(
            webhooks=[
                {
                    "webhook": "github-ci",
                    "secret": "secret-1",
                    "enabled": True,
                    "created_at": "2026-03-19 10:00:00",
                }
            ]
        )


def _build_service(
    *,
    get_run_status_use_case: _FakeGetRunStatusUseCase | None = None,
    handle_input_use_case: _FakeHandleInputUseCase | None = None,
    handle_webhook_use_case: _FakeHandleWebhookUseCase | None = None,
    worker_final_status: str = "SUCCEEDED",
) -> tuple[
    RuntimeApplicationService,
    _FakeAppendRuntimeEventUseCase,
    _FakeCreateRunUseCase,
    _FakeGetStartStepUseCase,
    _FakeRunWorkerService,
]:
    append_runtime_event_use_case = _FakeAppendRuntimeEventUseCase()
    create_run_use_case = _FakeCreateRunUseCase()
    status_use_case = get_run_status_use_case or _FakeGetRunStatusUseCase()
    get_start_step_use_case = _FakeGetStartStepUseCase(run_status_use_case=status_use_case)
    run_worker_service = _FakeRunWorkerService(
        run_status_use_case=status_use_case,
        final_status=worker_final_status,
    )
    service = RuntimeApplicationService(
        bootstrap_runtime_use_case=BootstrapRuntimeUseCase(
            store=SimpleNamespace(init_db=lambda: None),
            execution_output_store=SimpleNamespace(init_db=lambda: None),
            webhook_registry=SimpleNamespace(init_db=lambda: None),
        ),
        append_runtime_event_use_case=append_runtime_event_use_case,
        create_run_use_case=create_run_use_case,
        fail_run_use_case=_FakeFailRunUseCase(),
        get_start_step_use_case=get_start_step_use_case,
        handle_input_use_case=handle_input_use_case or _FakeHandleInputUseCase(),
        handle_webhook_use_case=handle_webhook_use_case or _FakeHandleWebhookUseCase(),
        list_webhooks_use_case=_FakeListWebhooksUseCase(),
        register_webhook_use_case=_FakeRegisterWebhookUseCase(),
        remove_webhook_use_case=_FakeRemoveWebhookUseCase(),
        resume_run_use_case=_FakeResumeRunUseCase(),
        get_run_status_use_case=status_use_case,
        run_worker_service=run_worker_service,
    )
    return (
        service,
        append_runtime_event_use_case,
        create_run_use_case,
        get_start_step_use_case,
        run_worker_service,
    )


def test_create_run_only_creates_run() -> None:
    (
        service,
        append_runtime_event_use_case,
        create_run_use_case,
        get_start_step_use_case,
        run_worker_service,
    ) = _build_service()

    result = service.create_run("notify_test", {"message": "ok"}, skill_source="internal")

    assert result == {"run_id": "run-1", "status": "CREATED"}
    assert create_run_use_case.calls == [
        {
            "skill_ref": "notify_test",
            "inputs": {"message": "ok"},
            "skill_source": "internal",
        }
    ]
    assert get_start_step_use_case.calls == []
    assert run_worker_service.calls == []
    assert append_runtime_event_use_case.calls == [
        {
            "run_id": "run-1",
            "event_type": RuntimeEventType.RUN_CREATE,
            "payload": {"skill": "notify_test", "skill_source": "internal"},
        }
    ]


def test_run_prepares_dispatches_and_reads_final_status() -> None:
    get_run_status_use_case = _FakeGetRunStatusUseCase(status="WAITING")
    (
        service,
        _append_runtime_event_use_case,
        _create_run_use_case,
        get_start_step_use_case,
        run_worker_service,
    ) = _build_service(
        get_run_status_use_case=get_run_status_use_case,
        worker_final_status="WAITING",
    )

    result = service.run("notify_test", {})

    assert result == {"run_id": "run-1", "status": "WAITING"}
    assert get_start_step_use_case.calls == ["run-1"]
    assert run_worker_service.calls == ["run-1"]
    assert get_run_status_use_case.calls == ["run-1"]


def test_start_worker_prepares_created_run() -> None:
    (
        service,
        _append_runtime_event_use_case,
        _create_run_use_case,
        get_start_step_use_case,
        run_worker_service,
    ) = _build_service()

    result = service.start_worker("run-1")

    assert result == {"run_id": "run-1", "start_status": "PREPARED", "status": "CREATED"}
    assert get_start_step_use_case.calls == ["run-1"]
    assert run_worker_service.calls == []


def test_run_worker_dispatches_prepared_run() -> None:
    get_run_status_use_case = _FakeGetRunStatusUseCase(status="RUNNING", current="start")
    (
        service,
        _append_runtime_event_use_case,
        _create_run_use_case,
        _get_start_step_use_case,
        run_worker_service,
    ) = _build_service(
        get_run_status_use_case=get_run_status_use_case,
    )
    service.prepare_run("run-1")

    result = service.run_worker("run-1")

    assert result == {"run_id": "run-1", "status": "SUCCEEDED"}
    assert run_worker_service.calls == ["run-1"]


def test_handle_webhook_only_returns_matched_runs() -> None:
    (
        service,
        _append_runtime_event_use_case,
        _create_run_use_case,
        _get_start_step_use_case,
        run_worker_service,
    ) = _build_service(
        handle_webhook_use_case=_FakeHandleWebhookUseCase(run_ids=["run-1", "run-2"]),
    )

    result = service.handle_webhook("github", "42", {"ok": True}, dedup_key="delivery-1")

    assert result == {
        "accepted": True,
        "duplicate": False,
        "webhook": "github",
        "key": "42",
        "matched_runs": ["run-1", "run-2"],
    }
    assert run_worker_service.calls == []


def test_handle_input_only_returns_matched_runs() -> None:
    (
        service,
        _append_runtime_event_use_case,
        _create_run_use_case,
        _get_start_step_use_case,
        run_worker_service,
    ) = _build_service(
        handle_input_use_case=_FakeHandleInputUseCase(run_ids=["run-1"]),
    )

    result = service.handle_input("run-1", text="hello")

    assert result == {
        "accepted": True,
        "run_id": "run-1",
        "matched_runs": ["run-1"],
    }
    assert run_worker_service.calls == []


def test_list_webhooks_returns_registered_channels() -> None:
    (
        service,
        _append_runtime_event_use_case,
        _create_run_use_case,
        _get_start_step_use_case,
        _run_worker_service,
    ) = _build_service()

    result = service.list_webhooks()

    assert result == [
        {
            "webhook": "github-ci",
            "secret": "secret-1",
            "enabled": True,
            "created_at": "2026-03-19 10:00:00",
        }
    ]


def test_resume_run_emits_runtime_event_and_dispatches_worker() -> None:
    get_run_status_use_case = _FakeGetRunStatusUseCase(status="WAITING")
    append_runtime_event_use_case = _FakeAppendRuntimeEventUseCase()
    resume_run_use_case = _FakeResumeRunUseCase(status=ResumeRunStatus.RESUMED)
    run_worker_service = _FakeRunWorkerService(
        run_status_use_case=get_run_status_use_case,
        final_status="WAITING",
    )

    service = RuntimeApplicationService(
        bootstrap_runtime_use_case=BootstrapRuntimeUseCase(
            store=SimpleNamespace(init_db=lambda: None),
            execution_output_store=SimpleNamespace(init_db=lambda: None),
            webhook_registry=SimpleNamespace(init_db=lambda: None),
        ),
        append_runtime_event_use_case=append_runtime_event_use_case,
        create_run_use_case=_FakeCreateRunUseCase(),
        fail_run_use_case=_FakeFailRunUseCase(),
        get_start_step_use_case=_FakeGetStartStepUseCase(
            run_status_use_case=get_run_status_use_case
        ),
        handle_input_use_case=_FakeHandleInputUseCase(),
        handle_webhook_use_case=_FakeHandleWebhookUseCase(),
        list_webhooks_use_case=_FakeListWebhooksUseCase(),
        register_webhook_use_case=_FakeRegisterWebhookUseCase(),
        remove_webhook_use_case=_FakeRemoveWebhookUseCase(),
        resume_run_use_case=resume_run_use_case,
        get_run_status_use_case=get_run_status_use_case,
        run_worker_service=run_worker_service,
    )

    result = service.resume_run("run-1")

    assert result == {
        "run_id": "run-1",
        "resume_status": "RESUMED",
        "status": "WAITING",
    }
    assert resume_run_use_case.calls == [{"run_id": "run-1", "source": "manual"}]
    assert append_runtime_event_use_case.calls == [
        {
            "run_id": "run-1",
            "event_type": RuntimeEventType.RUN_RESUME,
            "payload": {"source": "manual"},
        }
    ]
    assert run_worker_service.calls == ["run-1"]
