from types import SimpleNamespace

import pytest

from skiller.interfaces.cli import main as cli_main


class _FakeController:
    def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        _ = (args, kwargs)
        self.create_run_calls: list[tuple[str, dict[str, str], str]] = []
        self.start_worker_calls: list[str] = []
        self.run_worker_calls: list[str] = []
        self.resume_calls: list[str] = []
        self.receive_input_calls: list[tuple[str, str]] = []
        self.receive_calls: list[tuple[str, str, dict[str, str], str | None]] = []
        self.logs_calls: list[str] = []
        self.execution_output_calls: list[str] = []
        self.status_calls: list[str] = []
        self.list_runs_calls: list[tuple[int, list[str] | None]] = []
        self.run_result = {"run_id": "run-1", "status": "CREATED"}
        self.start_worker_result = {
            "run_id": "run-1",
            "start_status": "PREPARED",
            "status": "CREATED",
        }
        self.run_worker_result = {"run_id": "run-1", "status": "SUCCEEDED"}
        self.run_error: ValueError | None = None
        self.logs_result = [
            {
                "id": "evt-1",
                "type": "STEP_SUCCESS",
                "payload": {
                    "step": "done",
                    "step_type": "notify",
                    "output": {"text": "done", "value": {"message": "done"}, "body_ref": None},
                },
            }
        ]
        self.status_results: list[dict[str, object]] = [
            {"id": "run-1", "status": "RUNNING"},
            {"id": "run-1", "status": "SUCCEEDED"},
        ]
        self.list_runs_result: list[dict[str, object]] = [
            {
                "id": "run-1",
                "status": "WAITING",
                "skill_ref": "webhook_signal_oracle",
                "current": "wait_signal",
                "updated_at": "2026-03-18 11:42:10",
            }
        ]
        self.list_webhooks_result: list[dict[str, object]] = [
            {
                "webhook": "github-ci",
                "secret": "secret-123",
                "enabled": True,
                "created_at": "2026-03-19 10:00:00",
            }
        ]

    def initialize(self) -> None:
        return None

    def create_run(
        self,
        skill_ref: str,
        inputs: dict[str, str],
        *,
        skill_source: str = "internal",
    ) -> dict[str, str]:
        if self.run_error is not None:
            raise self.run_error
        self.create_run_calls.append((skill_ref, inputs, skill_source))
        return dict(self.run_result)

    def start_worker(self, run_id: str) -> dict[str, str]:
        self.start_worker_calls.append(run_id)
        return dict(self.start_worker_result)

    def run_worker(self, run_id: str) -> dict[str, str]:
        self.run_worker_calls.append(run_id)
        return dict(self.run_worker_result)

    def resume(self, run_id: str) -> dict[str, str]:
        self.resume_calls.append(run_id)
        return {"run_id": run_id, "resume_status": "RESUMED", "status": "WAITING"}

    def logs(self, run_id: str) -> list[dict[str, object]]:
        self.logs_calls.append(run_id)
        return list(self.logs_result)

    def get_execution_output(self, body_ref: str) -> dict[str, object] | None:
        self.execution_output_calls.append(body_ref)
        return {"data": {"reply": "hola"}}

    def status(self, run_id: str) -> dict[str, object] | None:
        self.status_calls.append(run_id)
        if not self.status_results:
            return None
        if len(self.status_results) == 1:
            return dict(self.status_results[0])
        return dict(self.status_results.pop(0))

    def list_runs(
        self,
        *,
        limit: int = 20,
        statuses: list[str] | None = None,
    ) -> list[dict[str, object]]:
        self.list_runs_calls.append((limit, statuses))
        return list(self.list_runs_result)

    def receive_webhook(
        self,
        webhook: str,
        key: str,
        payload: dict[str, str],
        dedup_key: str | None = None,
    ) -> dict[str, object]:
        self.receive_calls.append((webhook, key, payload, dedup_key))
        return {
            "accepted": True,
            "duplicate": False,
            "webhook": webhook,
            "key": key,
            "matched_runs": ["run-1"],
        }

    def receive_input(self, run_id: str, *, text: str) -> dict[str, object]:
        self.receive_input_calls.append((run_id, text))
        return {
            "accepted": True,
            "run_id": run_id,
            "matched_runs": [run_id],
        }

    def register_webhook(self, webhook: str) -> dict[str, object]:
        return {
            "webhook": webhook,
            "status": "REGISTERED",
            "secret": "secret-123",
            "enabled": True,
        }

    def list_webhooks(self) -> list[dict[str, object]]:
        return list(self.list_webhooks_result)

    def remove_webhook(self, webhook: str) -> dict[str, object]:
        return {
            "webhook": webhook,
            "status": "REMOVED",
            "removed": True,
        }


@pytest.fixture
def fake_container() -> SimpleNamespace:
    return SimpleNamespace(
        runtime_service=object(),
        query_service=object(),
        settings=SimpleNamespace(
            db_path="/tmp/test.db", webhooks_host="127.0.0.1", webhooks_port=8001
        ),
    )


class _FakeWorkerProcessService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def start(self, run_id: str) -> SimpleNamespace:
        self.calls.append(("start", run_id))
        return SimpleNamespace(command="start", pid=101, run_id=run_id)

    def run(self, run_id: str) -> SimpleNamespace:
        self.calls.append(("run", run_id))
        return SimpleNamespace(command="run", pid=202, run_id=run_id)

    def resume(self, run_id: str) -> SimpleNamespace:
        self.calls.append(("resume", run_id))
        return SimpleNamespace(command="resume", pid=303, run_id=run_id)


def test_run_internal_skill_by_name(
    monkeypatch: pytest.MonkeyPatch,
    fake_container: SimpleNamespace,
    capsys: pytest.CaptureFixture[str],
) -> None:
    controller = _FakeController(None, None, None)
    worker_process_service = _FakeWorkerProcessService()

    monkeypatch.setattr(cli_main, "build_runtime_container", lambda: fake_container)
    monkeypatch.setattr(cli_main, "RuntimeController", lambda **_: controller)
    monkeypatch.setattr(cli_main, "WorkerProcessService", lambda: worker_process_service)
    monkeypatch.setattr(cli_main.time, "sleep", lambda _: None)

    exit_code = cli_main.main(["run", "notify_test", "--arg", "message=ok"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert controller.create_run_calls == [("notify_test", {"message": "ok"}, "internal")]
    assert worker_process_service.calls == [("start", "run-1")]
    assert '"run_id": "run-1"' in captured.out
    assert '"worker_pid": 101' in captured.out
    assert '"status": "SUCCEEDED"' in captured.out
    assert "[1] CREATED" in captured.err
    assert "[1] RUNNING" in captured.err
    assert "[1] STEP_SUCCESS" in captured.err
    assert "[1] SUCCEEDED" in captured.err


def test_run_external_skill_by_file(
    monkeypatch: pytest.MonkeyPatch,
    fake_container: SimpleNamespace,
    capsys: pytest.CaptureFixture[str],
) -> None:
    controller = _FakeController(None, None, None)
    worker_process_service = _FakeWorkerProcessService()

    monkeypatch.setattr(cli_main, "build_runtime_container", lambda: fake_container)
    monkeypatch.setattr(cli_main, "RuntimeController", lambda **_: controller)
    monkeypatch.setattr(cli_main, "WorkerProcessService", lambda: worker_process_service)
    monkeypatch.setattr(cli_main.time, "sleep", lambda _: None)

    exit_code = cli_main.main(["run", "--file", "/tmp/demo.yaml", "--arg", "message=ok"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert controller.create_run_calls == [("/tmp/demo.yaml", {"message": "ok"}, "file")]
    assert '"status": "SUCCEEDED"' in captured.out


def test_run_can_include_logs_in_response(
    monkeypatch: pytest.MonkeyPatch,
    fake_container: SimpleNamespace,
    capsys: pytest.CaptureFixture[str],
) -> None:
    controller = _FakeController(None, None, None)
    worker_process_service = _FakeWorkerProcessService()

    monkeypatch.setattr(cli_main, "build_runtime_container", lambda: fake_container)
    monkeypatch.setattr(cli_main, "RuntimeController", lambda **_: controller)
    monkeypatch.setattr(cli_main, "WorkerProcessService", lambda: worker_process_service)
    monkeypatch.setattr(cli_main.time, "sleep", lambda _: None)

    exit_code = cli_main.main(["run", "notify_test", "--logs"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert controller.logs_calls[-1] == "run-1"
    assert '"logs": [' in captured.out
    assert '"type": "STEP_SUCCESS"' in captured.out


def test_run_can_start_webhooks_when_waiting(
    monkeypatch: pytest.MonkeyPatch,
    fake_container: SimpleNamespace,
    capsys: pytest.CaptureFixture[str],
) -> None:
    controller = _FakeController(None, None, None)
    worker_process_service = _FakeWorkerProcessService()

    class _FakeWebhookProcessService:
        def __init__(self, settings) -> None:  # noqa: ANN001
            self.settings = settings

        def start(self):
            return SimpleNamespace(endpoint="http://127.0.0.1:8001/health", pid=1234, started=True)

    monkeypatch.setattr(cli_main, "build_runtime_container", lambda: fake_container)
    monkeypatch.setattr(cli_main, "RuntimeController", lambda **_: controller)
    monkeypatch.setattr(cli_main, "WebhookProcessService", _FakeWebhookProcessService)
    monkeypatch.setattr(cli_main, "WorkerProcessService", lambda: worker_process_service)
    monkeypatch.setattr(cli_main.time, "sleep", lambda _: None)

    exit_code = cli_main.main(["run", "notify_test", "--start-webhooks"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"status": "SUCCEEDED"' in captured.out
    assert '"webhooks_started": true' in captured.out
    assert '"webhooks_pid": 1234' in captured.out


def test_run_waiting_result_includes_waiting_metadata(
    monkeypatch: pytest.MonkeyPatch,
    fake_container: SimpleNamespace,
    capsys: pytest.CaptureFixture[str],
) -> None:
    controller = _FakeController(None, None, None)
    controller.status_results = [
        {
            "id": "run-1",
            "status": "WAITING",
            "current": "ask_user",
            "wait_type": "input",
            "prompt": "Write a short summary",
        }
    ]
    worker_process_service = _FakeWorkerProcessService()

    monkeypatch.setattr(cli_main, "build_runtime_container", lambda: fake_container)
    monkeypatch.setattr(cli_main, "RuntimeController", lambda **_: controller)
    monkeypatch.setattr(cli_main, "WorkerProcessService", lambda: worker_process_service)
    monkeypatch.setattr(cli_main.time, "sleep", lambda _: None)

    exit_code = cli_main.main(["run", "wait_input_test"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"status": "WAITING"' in captured.out
    assert '"wait_type": "input"' in captured.out
    assert '"prompt": "Write a short summary"' in captured.out


def test_run_fails_when_webhooks_requested_but_process_does_not_start(
    monkeypatch: pytest.MonkeyPatch,
    fake_container: SimpleNamespace,
    capsys: pytest.CaptureFixture[str],
) -> None:
    controller = _FakeController(None, None, None)
    worker_process_service = _FakeWorkerProcessService()

    class _FakeWebhookProcessService:
        def __init__(self, settings) -> None:  # noqa: ANN001
            self.settings = settings

        def start(self):
            raise RuntimeError("webhooks process did not become ready")

    monkeypatch.setattr(cli_main, "build_runtime_container", lambda: fake_container)
    monkeypatch.setattr(cli_main, "RuntimeController", lambda **_: controller)
    monkeypatch.setattr(cli_main, "WebhookProcessService", _FakeWebhookProcessService)
    monkeypatch.setattr(cli_main, "WorkerProcessService", lambda: worker_process_service)

    exit_code = cli_main.main(["run", "notify_test", "--start-webhooks"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert '"status": "CREATED"' in captured.out
    assert '"webhooks_started": false' in captured.out
    assert "webhooks process did not become ready" in captured.out


def test_run_failure_with_start_webhooks_can_include_logs(
    monkeypatch: pytest.MonkeyPatch,
    fake_container: SimpleNamespace,
    capsys: pytest.CaptureFixture[str],
) -> None:
    controller = _FakeController(None, None, None)
    worker_process_service = _FakeWorkerProcessService()

    class _FakeWebhookProcessService:
        def __init__(self, settings) -> None:  # noqa: ANN001
            self.settings = settings

        def start(self):
            raise RuntimeError("webhooks process did not become ready")

    monkeypatch.setattr(cli_main, "build_runtime_container", lambda: fake_container)
    monkeypatch.setattr(cli_main, "RuntimeController", lambda **_: controller)
    monkeypatch.setattr(cli_main, "WebhookProcessService", _FakeWebhookProcessService)
    monkeypatch.setattr(cli_main, "WorkerProcessService", lambda: worker_process_service)

    exit_code = cli_main.main(["run", "notify_test", "--start-webhooks", "--logs"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert controller.logs_calls == ["run-1"]
    assert '"logs": [' in captured.out


def test_run_rejects_missing_or_duplicated_skill_selection(
    monkeypatch: pytest.MonkeyPatch, fake_container: SimpleNamespace
) -> None:
    monkeypatch.setattr(cli_main, "build_runtime_container", lambda: fake_container)
    monkeypatch.setattr(cli_main, "RuntimeController", _FakeController)

    with pytest.raises(SystemExit) as missing:
        cli_main.main(["run"])
    assert missing.value.code == 2

    with pytest.raises(SystemExit) as duplicated:
        cli_main.main(["run", "notify_test", "--file", "/tmp/demo.yaml"])
    assert duplicated.value.code == 2


def test_resume_run(
    monkeypatch: pytest.MonkeyPatch,
    fake_container: SimpleNamespace,
    capsys: pytest.CaptureFixture[str],
) -> None:
    controller = _FakeController(None, None, None)
    worker_process_service = _FakeWorkerProcessService()

    monkeypatch.setattr(cli_main, "build_runtime_container", lambda: fake_container)
    monkeypatch.setattr(cli_main, "RuntimeController", lambda **_: controller)
    monkeypatch.setattr(cli_main, "WorkerProcessService", lambda: worker_process_service)

    exit_code = cli_main.main(["resume", "run-123"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert controller.resume_calls == []
    assert worker_process_service.calls == [("resume", "run-123")]
    assert '"resume_status": "DISPATCHED"' in captured.out


def test_worker_start_prepares_and_launches_execution(
    monkeypatch: pytest.MonkeyPatch,
    fake_container: SimpleNamespace,
    capsys: pytest.CaptureFixture[str],
) -> None:
    controller = _FakeController(None, None, None)
    worker_process_service = _FakeWorkerProcessService()

    monkeypatch.setattr(cli_main, "build_runtime_container", lambda: fake_container)
    monkeypatch.setattr(cli_main, "RuntimeController", lambda **_: controller)
    monkeypatch.setattr(cli_main, "WorkerProcessService", lambda: worker_process_service)

    exit_code = cli_main.main(["worker", "start", "run-123"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert controller.start_worker_calls == ["run-123"]
    assert worker_process_service.calls == [("run", "run-123")]
    assert '"start_status": "PREPARED"' in captured.out


def test_worker_run_executes_prepared_run(
    monkeypatch: pytest.MonkeyPatch,
    fake_container: SimpleNamespace,
    capsys: pytest.CaptureFixture[str],
) -> None:
    controller = _FakeController(None, None, None)

    monkeypatch.setattr(cli_main, "build_runtime_container", lambda: fake_container)
    monkeypatch.setattr(cli_main, "RuntimeController", lambda **_: controller)

    exit_code = cli_main.main(["worker", "run", "run-123"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert controller.run_worker_calls == ["run-123"]
    assert '"status": "SUCCEEDED"' in captured.out


def test_worker_resume_reuses_runtime_resume(
    monkeypatch: pytest.MonkeyPatch,
    fake_container: SimpleNamespace,
    capsys: pytest.CaptureFixture[str],
) -> None:
    controller = _FakeController(None, None, None)

    monkeypatch.setattr(cli_main, "build_runtime_container", lambda: fake_container)
    monkeypatch.setattr(cli_main, "RuntimeController", lambda **_: controller)

    exit_code = cli_main.main(["worker", "resume", "run-123"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert controller.resume_calls == ["run-123"]
    assert '"resume_status": "RESUMED"' in captured.out


def test_watch_prints_progress_and_final_status(
    monkeypatch: pytest.MonkeyPatch,
    fake_container: SimpleNamespace,
    capsys: pytest.CaptureFixture[str],
) -> None:
    controller = _FakeController(None, None, None)
    controller.status_results = [
        {"id": "run-123", "status": "RUNNING"},
        {"id": "run-123", "status": "WAITING"},
    ]
    controller.logs_result = [
        {
            "id": "evt-1",
            "type": "RUN_WAITING",
            "payload": {
                "step": "wait_signal",
                "step_type": "wait_webhook",
                "output": {
                    "text": "Waiting webhook: test:42.",
                    "value": {"webhook": "test", "key": "42"},
                    "body_ref": None,
                },
            },
        }
    ]

    monkeypatch.setattr(cli_main, "build_runtime_container", lambda: fake_container)
    monkeypatch.setattr(cli_main, "RuntimeController", lambda **_: controller)
    monkeypatch.setattr(cli_main.time, "sleep", lambda _: None)

    exit_code = cli_main.main(["watch", "run-123"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"run_id": "run-123"' in captured.out
    assert '"status": "WAITING"' in captured.out
    assert '"events": [' in captured.out
    assert "[123] RUNNING" in captured.err
    assert (
        '[123] RUN_WAITING step="wait_signal" step_type="wait_webhook" '
        'output={"body_ref":null,"text":"Waiting webhook: test:42.",'
        '"value":{"key":"42","webhook":"test"}}'
    ) in captured.err


def test_status_can_include_waiting_metadata(
    monkeypatch: pytest.MonkeyPatch,
    fake_container: SimpleNamespace,
    capsys: pytest.CaptureFixture[str],
) -> None:
    controller = _FakeController(None, None, None)
    controller.status_results = [
        {
            "id": "run-1",
            "skill_ref": "webhook_signal_oracle",
            "status": "WAITING",
            "current": "wait_signal",
            "wait_type": "webhook",
            "webhook": "market-signal",
            "key": "btc-usd",
        }
    ]

    monkeypatch.setattr(cli_main, "build_runtime_container", lambda: fake_container)
    monkeypatch.setattr(cli_main, "RuntimeController", lambda **_: controller)

    exit_code = cli_main.main(["status", "run-1"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"wait_type": "webhook"' in captured.out
    assert '"webhook": "market-signal"' in captured.out
    assert '"key": "btc-usd"' in captured.out


def test_execution_output_returns_persisted_body(
    monkeypatch: pytest.MonkeyPatch,
    fake_container: SimpleNamespace,
    capsys: pytest.CaptureFixture[str],
) -> None:
    controller = _FakeController(None, None, None)

    monkeypatch.setattr(cli_main, "build_runtime_container", lambda: fake_container)
    monkeypatch.setattr(cli_main, "RuntimeController", lambda **_: controller)

    exit_code = cli_main.main(["execution-output", "execution_output:1"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert controller.execution_output_calls == ["execution_output:1"]
    assert '"reply": "hola"' in captured.out


def test_runs_lists_recent_runs(
    monkeypatch: pytest.MonkeyPatch,
    fake_container: SimpleNamespace,
    capsys: pytest.CaptureFixture[str],
) -> None:
    controller = _FakeController(None, None, None)

    monkeypatch.setattr(cli_main, "build_runtime_container", lambda: fake_container)
    monkeypatch.setattr(cli_main, "RuntimeController", lambda **_: controller)

    exit_code = cli_main.main(["runs", "--limit", "5"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert controller.list_runs_calls == [(5, [])]
    assert '"id": "run-1"' in captured.out
    assert '"skill_ref": "webhook_signal_oracle"' in captured.out


def test_runs_accepts_status_filters(
    monkeypatch: pytest.MonkeyPatch,
    fake_container: SimpleNamespace,
    capsys: pytest.CaptureFixture[str],
) -> None:
    controller = _FakeController(None, None, None)

    monkeypatch.setattr(cli_main, "build_runtime_container", lambda: fake_container)
    monkeypatch.setattr(cli_main, "RuntimeController", lambda **_: controller)

    exit_code = cli_main.main(["runs", "--status", "waiting", "--limit", "5"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert controller.list_runs_calls == [(5, ["WAITING"])]
    assert '"status": "WAITING"' in captured.out


def test_webhook_receive_uses_webhook_and_key(
    monkeypatch: pytest.MonkeyPatch,
    fake_container: SimpleNamespace,
    capsys: pytest.CaptureFixture[str],
) -> None:
    controller = _FakeController(None, None, None)
    worker_process_service = _FakeWorkerProcessService()

    monkeypatch.setattr(cli_main, "build_runtime_container", lambda: fake_container)
    monkeypatch.setattr(cli_main, "RuntimeController", lambda **_: controller)
    monkeypatch.setattr(cli_main, "WorkerProcessService", lambda: worker_process_service)

    exit_code = cli_main.main(
        ["webhook", "receive", "github-pr-merged", "42", "--json", '{"ok":true}']
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert controller.receive_calls == [("github-pr-merged", "42", {"ok": True}, None)]
    assert worker_process_service.calls == [("resume", "run-1")]
    assert '"accepted": true' in captured.out
    assert '"duplicate": false' in captured.out
    assert '"matched_runs": [' in captured.out
    assert '"resumed_runs": [' in captured.out


def test_input_receive_uses_run_id_and_text(
    monkeypatch: pytest.MonkeyPatch,
    fake_container: SimpleNamespace,
    capsys: pytest.CaptureFixture[str],
) -> None:
    controller = _FakeController(None, None, None)
    worker_process_service = _FakeWorkerProcessService()

    monkeypatch.setattr(cli_main, "build_runtime_container", lambda: fake_container)
    monkeypatch.setattr(cli_main, "RuntimeController", lambda **_: controller)
    monkeypatch.setattr(cli_main, "WorkerProcessService", lambda: worker_process_service)

    exit_code = cli_main.main(["input", "receive", "run-1", "--text", "database timeout"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert controller.receive_input_calls == [("run-1", "database timeout")]
    assert worker_process_service.calls == [("resume", "run-1")]
    assert '"accepted": true' in captured.out
    assert '"matched_runs": [' in captured.out
    assert '"resumed_runs": [' in captured.out


def test_webhook_register(
    monkeypatch: pytest.MonkeyPatch,
    fake_container: SimpleNamespace,
    capsys: pytest.CaptureFixture[str],
) -> None:
    controller = _FakeController(None, None, None)

    monkeypatch.setattr(cli_main, "build_runtime_container", lambda: fake_container)
    monkeypatch.setattr(cli_main, "RuntimeController", lambda **_: controller)

    exit_code = cli_main.main(["webhook", "register", "github-ci"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"status": "REGISTERED"' in captured.out
    assert '"secret": "secret-123"' in captured.out
    assert '"webhook_url": "http://127.0.0.1:8001/webhooks/github-ci/{key}"' in captured.out


def test_webhook_list(
    monkeypatch: pytest.MonkeyPatch,
    fake_container: SimpleNamespace,
    capsys: pytest.CaptureFixture[str],
) -> None:
    controller = _FakeController(None, None, None)

    monkeypatch.setattr(cli_main, "build_runtime_container", lambda: fake_container)
    monkeypatch.setattr(cli_main, "RuntimeController", lambda **_: controller)

    exit_code = cli_main.main(["webhook", "list"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"webhook": "github-ci"' in captured.out
    assert '"enabled": true' in captured.out


def test_webhook_remove(
    monkeypatch: pytest.MonkeyPatch,
    fake_container: SimpleNamespace,
    capsys: pytest.CaptureFixture[str],
) -> None:
    controller = _FakeController(None, None, None)

    monkeypatch.setattr(cli_main, "build_runtime_container", lambda: fake_container)
    monkeypatch.setattr(cli_main, "RuntimeController", lambda **_: controller)

    exit_code = cli_main.main(["webhook", "remove", "github-ci"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"status": "REMOVED"' in captured.out
    assert '"removed": true' in captured.out
