import json
from types import SimpleNamespace
from typing import Any

import pytest

from skiller.interfaces.cli import main as cli_main

SKILL_NAME = "unit_skill"
SKILL_FILE = "/virtual/unit_skill"


class _FakeController:
    def __init__(self, *args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        self.initialized = False
        self.create_run_calls: list[tuple[str, dict[str, str], str]] = []
        self.start_worker_calls: list[str] = []
        self.run_worker_calls: list[str] = []
        self.resume_calls: list[str] = []
        self.interrupt_agent_calls: list[str] = []
        self.agent_model_calls: list[dict[str, str]] = []
        self.agent_stats_calls: list[dict[str, str]] = []
        self.action_done_calls: list[dict[str, str]] = []
        self.delete_run_calls: list[str] = []
        self.receive_input_calls: list[tuple[str, str]] = []
        self.receive_webhook_calls: list[tuple[str, str, dict[str, object], str | None]] = []
        self.receive_channel_calls: list[
            tuple[str, str, dict[str, object], str | None, str | None]
        ] = []
        self.register_webhook_calls: list[tuple[str, str, str, str]] = []
        self.logs_calls: list[dict[str, object]] = []
        self.status_calls: list[dict[str, object]] = []
        self.list_runs_calls: list[tuple[int, list[str]]] = []
        self.run_result: dict[str, object] = {"run_id": "run-1", "status": "CREATED"}
        self.start_worker_result: dict[str, object] = {
            "run_id": "run-1",
            "start_status": "PREPARED",
            "status": "CREATED",
        }
        self.run_worker_result: dict[str, object] = {
            "run_id": "run-1",
            "status": "SUCCEEDED",
        }
        self.logs_result: list[dict[str, object]] = [
            {
                "id": "evt-1",
                "type": "STEP_SUCCESS",
                "payload": {
                    "output": {
                        "text": "done",
                        "value": {"message": "done", "format": "simple"},
                        "body_ref": None,
                    },
                    "next": None,
                },
            }
        ]
        self.status_results: list[dict[str, object]] = [
            {"run_id": "run-1", "status": "RUNNING"},
            {"run_id": "run-1", "status": "SUCCEEDED"},
        ]
        self.list_runs_result: list[dict[str, object]] = [
            {
                "id": "run-1",
                "status": "WAITING",
                "ref": "unit_skill",
                "current": "wait_signal",
            }
        ]
        self.list_webhooks_result: list[dict[str, object]] = [
            {
                "webhook": "github-ci",
                "secret": "secret-123",
                "method": "POST",
                "auth": "signed",
                "payload_source": "body_json",
                "enabled": True,
            }
        ]

    def initialize(self) -> None:
        self.initialized = True

    def create_run(
        self,
        skill_ref: str,
        inputs: dict[str, str],
        *,
        skill_source: str = "internal",
    ) -> dict[str, object]:
        self.create_run_calls.append((skill_ref, inputs, skill_source))
        return dict(self.run_result)

    def start_worker(self, run_id: str) -> dict[str, object]:
        self.start_worker_calls.append(run_id)
        return dict(self.start_worker_result)

    def run_worker(self, run_id: str) -> dict[str, object]:
        self.run_worker_calls.append(run_id)
        return dict(self.run_worker_result)

    def resume(self, run_id: str) -> dict[str, object]:
        self.resume_calls.append(run_id)
        return {"run_id": run_id, "resume_status": "RESUMED", "status": "WAITING"}

    def interrupt_agent(self, run_id: str) -> dict[str, object]:
        self.interrupt_agent_calls.append(run_id)
        return {
            "run_id": run_id,
            "status": "ENQUEUED",
            "enqueued": True,
            "item": {"type": "agent_interrupt"},
        }

    def agent_stats(self, run_id: str, agent_id: str) -> dict[str, object]:
        self.agent_stats_calls.append({"run_id": run_id, "agent_id": agent_id})
        return {
            "run_id": run_id,
            "agent_id": agent_id,
            "status": "OK",
            "ok": True,
            "context": {
                "entries": 3,
                "estimated_tokens": 125,
                "window": {
                    "start_sequence": 2,
                    "end_sequence": 3,
                    "current_tokens": 100,
                    "limit_tokens": 80000,
                    "capacity_tokens": 100000,
                },
            },
        }

    def agent_model(
        self,
        run_id: str,
        provider: str,
        model: str,
    ) -> dict[str, object]:
        self.agent_model_calls.append(
            {
                "run_id": run_id,
                "provider": provider,
                "model": model,
            }
        )
        return {
            "run_id": run_id,
            "provider": provider,
            "model": model,
            "status": "OK",
            "ok": True,
        }

    def action_done(self, run_id: str, step_id: str) -> dict[str, object]:
        self.action_done_calls.append({"run_id": run_id, "step_id": step_id})
        return {
            "run_id": run_id,
            "step_id": step_id,
            "status": "DONE",
            "done": True,
            "changed": True,
        }

    def delete_run(self, run_id: str) -> dict[str, object]:
        self.delete_run_calls.append(run_id)
        return {"run_id": run_id, "status": "DELETED", "deleted": True}

    def logs(
        self,
        run_id: str,
        *,
        after_sequence: int | None = None,
        limit: int | None = None,
    ) -> list[dict[str, object]]:
        self.logs_calls.append(
            {
                "run_id": run_id,
                "after_sequence": after_sequence,
                "limit": limit,
            }
        )
        return list(self.logs_result)

    def status(self, run_id: str) -> dict[str, object] | None:
        self.status_calls.append({"run_id": run_id})
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
        normalized_statuses = statuses or []
        self.list_runs_calls.append((limit, normalized_statuses))
        return list(self.list_runs_result)

    def receive_input(self, run_id: str, *, text: str) -> dict[str, object]:
        self.receive_input_calls.append((run_id, text))
        return {"accepted": True, "run_id": run_id, "matched_runs": [run_id]}

    def receive_webhook(
        self,
        webhook: str,
        key: str,
        payload: dict[str, object],
        dedup_key: str | None = None,
    ) -> dict[str, object]:
        self.receive_webhook_calls.append((webhook, key, payload, dedup_key))
        return {
            "accepted": True,
            "duplicate": False,
            "webhook": webhook,
            "key": key,
            "matched_runs": ["run-1"],
        }

    def receive_channel(
        self,
        channel: str,
        key: str,
        payload: dict[str, object],
        *,
        external_id: str | None = None,
        dedup_key: str | None = None,
    ) -> dict[str, object]:
        self.receive_channel_calls.append((channel, key, payload, external_id, dedup_key))
        return {
            "accepted": True,
            "duplicate": False,
            "channel": channel,
            "key": key,
            "matched_runs": ["run-1"],
        }

    def register_webhook(
        self,
        webhook: str,
        *,
        method: str = "POST",
        auth: str = "signed",
        payload_source: str = "body_json",
    ) -> dict[str, object]:
        self.register_webhook_calls.append((webhook, method, auth, payload_source))
        return {
            "webhook": webhook,
            "status": "REGISTERED",
            "method": method,
            "auth": auth,
            "payload_source": payload_source,
            "secret": "secret-123",
            "enabled": True,
        }

    def list_webhooks(self) -> list[dict[str, object]]:
        return list(self.list_webhooks_result)

    def remove_webhook(self, webhook: str) -> dict[str, object]:
        return {"webhook": webhook, "status": "REMOVED", "removed": True}


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


@pytest.fixture
def fake_container() -> SimpleNamespace:
    return SimpleNamespace(
        agent_service=object(),
        agent_mapper=object(),
        run_service=object(),
        run_mapper=object(),
        query_service=object(),
        status_mapper=object(),
        wait_service=object(),
        input_wait_mapper=object(),
        channel_wait_mapper=object(),
        webhook_wait_mapper=object(),
        settings=SimpleNamespace(
            db_path="/tmp/test.db",
            webhooks_host="127.0.0.1",
            webhooks_port=8001,
        ),
    )


def _install_runtime(
    monkeypatch: pytest.MonkeyPatch,
    fake_container: SimpleNamespace,
    controller: _FakeController,
    *,
    worker_process_service: _FakeWorkerProcessService | None = None,
) -> None:
    monkeypatch.setattr(cli_main, "build_runtime_container", lambda: fake_container)
    monkeypatch.setattr(cli_main, "RuntimeController", lambda **_: controller)
    if worker_process_service is not None:
        monkeypatch.setattr(
            cli_main,
            "WorkerProcessService",
            lambda: worker_process_service,
        )


def _read_json(capsys: pytest.CaptureFixture[str]) -> tuple[dict[str, Any], str]:
    captured = capsys.readouterr()
    return json.loads(captured.out), captured.err


def _read_json_list(capsys: pytest.CaptureFixture[str]) -> tuple[list[dict[str, Any]], str]:
    captured = capsys.readouterr()
    return json.loads(captured.out), captured.err


def test_main_without_args_runs_tui(monkeypatch: pytest.MonkeyPatch) -> None:
    called = {"run_tui": False}

    def fake_run_tui() -> str:
        called["run_tui"] = True
        return "session-key"

    monkeypatch.setattr(cli_main, "_load_tui_runner", lambda: fake_run_tui)

    exit_code = cli_main.main([])

    assert exit_code == 0
    assert called["run_tui"] is True


def test_version_prints_package_version(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(cli_main, "_get_package_version", lambda: "1.2.3")

    with pytest.raises(SystemExit) as exc:
        cli_main.main(["--version"])

    assert exc.value.code == 0
    assert capsys.readouterr().out == "skiller 1.2.3\n"


def test_run_internal_skill_dispatches_worker_and_watches_status(
    monkeypatch: pytest.MonkeyPatch,
    fake_container: SimpleNamespace,
    capsys: pytest.CaptureFixture[str],
) -> None:
    controller = _FakeController()
    worker_process_service = _FakeWorkerProcessService()
    _install_runtime(
        monkeypatch,
        fake_container,
        controller,
        worker_process_service=worker_process_service,
    )
    monkeypatch.setattr(cli_main.time, "sleep", lambda _: None)

    exit_code = cli_main.main(["run", SKILL_NAME, "--arg", "message=ok"])

    data, stderr = _read_json(capsys)
    assert exit_code == 0
    assert controller.initialized is True
    assert controller.create_run_calls == [(SKILL_NAME, {"message": "ok"}, "internal")]
    assert worker_process_service.calls == [("start", "run-1")]
    assert data["run_id"] == "run-1"
    assert data["worker_pid"] == 101
    assert data["status"] == "SUCCEEDED"
    assert "[1] CREATED" in stderr
    assert "[1] RUNNING" in stderr
    assert "[1] STEP_SUCCESS" in stderr
    assert "[1] SUCCEEDED" in stderr


def test_run_file_selection_forwards_path_without_loading_file(
    monkeypatch: pytest.MonkeyPatch,
    fake_container: SimpleNamespace,
    capsys: pytest.CaptureFixture[str],
) -> None:
    controller = _FakeController()
    worker_process_service = _FakeWorkerProcessService()
    _install_runtime(
        monkeypatch,
        fake_container,
        controller,
        worker_process_service=worker_process_service,
    )

    exit_code = cli_main.main(
        ["run", "--file", SKILL_FILE, "--arg", "message=ok", "--detach"]
    )

    data, stderr = _read_json(capsys)
    assert exit_code == 0
    assert controller.create_run_calls == [(SKILL_FILE, {"message": "ok"}, "file")]
    assert worker_process_service.calls == [("start", "run-1")]
    assert controller.status_calls == []
    assert controller.logs_calls == []
    assert data["status"] == "CREATED"
    assert stderr == ""


def test_run_waiting_result_merges_wait_metadata(
    monkeypatch: pytest.MonkeyPatch,
    fake_container: SimpleNamespace,
    capsys: pytest.CaptureFixture[str],
) -> None:
    controller = _FakeController()
    controller.status_results = [
        {
            "run_id": "run-1",
            "status": "WAITING",
            "wait_type": "input",
            "prompt": "Write a short summary",
        }
    ]
    worker_process_service = _FakeWorkerProcessService()
    _install_runtime(
        monkeypatch,
        fake_container,
        controller,
        worker_process_service=worker_process_service,
    )
    monkeypatch.setattr(cli_main.time, "sleep", lambda _: None)

    exit_code = cli_main.main(["run", SKILL_NAME])

    data, _ = _read_json(capsys)
    assert exit_code == 0
    assert data["status"] == "WAITING"
    assert data["wait_type"] == "input"
    assert data["prompt"] == "Write a short summary"


def test_run_can_start_server_before_dispatching_worker(
    monkeypatch: pytest.MonkeyPatch,
    fake_container: SimpleNamespace,
    capsys: pytest.CaptureFixture[str],
) -> None:
    controller = _FakeController()
    worker_process_service = _FakeWorkerProcessService()
    _install_runtime(
        monkeypatch,
        fake_container,
        controller,
        worker_process_service=worker_process_service,
    )
    monkeypatch.setattr(cli_main.time, "sleep", lambda _: None)

    class _FakeWebhookProcessService:
        def __init__(self, settings: object) -> None:
            self.settings = settings

        def start(self) -> SimpleNamespace:
            return SimpleNamespace(
                endpoint="http://127.0.0.1:8001/health",
                pid=1234,
                started=True,
                running=True,
                managed=True,
            )

    monkeypatch.setattr(cli_main, "WebhookProcessService", _FakeWebhookProcessService)

    exit_code = cli_main.main(["run", SKILL_NAME, "--start-server"])

    data, _ = _read_json(capsys)
    assert exit_code == 0
    assert data["server_started"] is True
    assert data["server_pid"] == 1234
    assert worker_process_service.calls == [("start", "run-1")]


def test_run_start_server_failure_can_include_logs(
    monkeypatch: pytest.MonkeyPatch,
    fake_container: SimpleNamespace,
    capsys: pytest.CaptureFixture[str],
) -> None:
    controller = _FakeController()
    worker_process_service = _FakeWorkerProcessService()
    _install_runtime(
        monkeypatch,
        fake_container,
        controller,
        worker_process_service=worker_process_service,
    )

    class _FakeWebhookProcessService:
        def __init__(self, settings: object) -> None:
            self.settings = settings

        def start(self) -> SimpleNamespace:
            raise RuntimeError("server process did not become ready")

    monkeypatch.setattr(cli_main, "WebhookProcessService", _FakeWebhookProcessService)

    exit_code = cli_main.main(["run", SKILL_NAME, "--start-server", "--logs"])

    data, _ = _read_json(capsys)
    assert exit_code == 1
    assert data["server_started"] is False
    assert data["error"] == "server process did not become ready"
    assert "logs" in data
    assert controller.logs_calls == [
        {
            "run_id": "run-1",
            "after_sequence": None,
            "limit": None,
        }
    ]
    assert worker_process_service.calls == []


def test_run_rejects_missing_or_duplicated_skill_selection(
    monkeypatch: pytest.MonkeyPatch,
    fake_container: SimpleNamespace,
) -> None:
    _install_runtime(monkeypatch, fake_container, _FakeController())

    with pytest.raises(SystemExit) as missing:
        cli_main.main(["run"])
    assert missing.value.code == 2

    with pytest.raises(SystemExit) as duplicated:
        cli_main.main(["run", SKILL_NAME, "--file", SKILL_FILE])
    assert duplicated.value.code == 2


def test_resume_dispatches_worker_process(
    monkeypatch: pytest.MonkeyPatch,
    fake_container: SimpleNamespace,
    capsys: pytest.CaptureFixture[str],
) -> None:
    controller = _FakeController()
    worker_process_service = _FakeWorkerProcessService()
    _install_runtime(
        monkeypatch,
        fake_container,
        controller,
        worker_process_service=worker_process_service,
    )

    exit_code = cli_main.main(["resume", "run-123"])

    data, _ = _read_json(capsys)
    assert exit_code == 0
    assert controller.resume_calls == []
    assert worker_process_service.calls == [("resume", "run-123")]
    assert data == {
        "run_id": "run-123",
        "resume_status": "DISPATCHED",
        "worker_pid": 303,
    }


def test_worker_start_prepares_run_and_launches_worker_process(
    monkeypatch: pytest.MonkeyPatch,
    fake_container: SimpleNamespace,
    capsys: pytest.CaptureFixture[str],
) -> None:
    controller = _FakeController()
    worker_process_service = _FakeWorkerProcessService()
    _install_runtime(
        monkeypatch,
        fake_container,
        controller,
        worker_process_service=worker_process_service,
    )

    exit_code = cli_main.main(["worker", "start", "run-123"])

    data, _ = _read_json(capsys)
    assert exit_code == 0
    assert controller.start_worker_calls == ["run-123"]
    assert worker_process_service.calls == [("run", "run-123")]
    assert data["start_status"] == "PREPARED"
    assert data["worker_pid"] == 202


@pytest.mark.parametrize(
    ("argv", "expected_call", "expected_status"),
    [
        (["worker", "run", "run-123"], "run_worker_calls", "SUCCEEDED"),
        (["worker", "resume", "run-123"], "resume_calls", "RESUMED"),
    ],
)
def test_worker_commands_delegate_to_runtime_controller(
    argv: list[str],
    expected_call: str,
    expected_status: str,
    monkeypatch: pytest.MonkeyPatch,
    fake_container: SimpleNamespace,
    capsys: pytest.CaptureFixture[str],
) -> None:
    controller = _FakeController()
    _install_runtime(monkeypatch, fake_container, controller)

    exit_code = cli_main.main(argv)

    data, _ = _read_json(capsys)
    assert exit_code == 0
    assert getattr(controller, expected_call) == ["run-123"]
    assert expected_status in data.values()


def test_logs_command_forwards_cursor_options(
    monkeypatch: pytest.MonkeyPatch,
    fake_container: SimpleNamespace,
    capsys: pytest.CaptureFixture[str],
) -> None:
    controller = _FakeController()
    _install_runtime(monkeypatch, fake_container, controller)

    exit_code = cli_main.main(["logs", "run-123", "--after", "10", "--limit", "50"])

    data, _ = _read_json_list(capsys)
    assert exit_code == 0
    assert controller.logs_calls == [
        {
            "run_id": "run-123",
            "after_sequence": 10,
            "limit": 50,
        }
    ]
    assert data[0]["type"] == "STEP_SUCCESS"


def test_logs_help_describes_raw_events_and_cursor(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc:
        cli_main.main(["logs", "--help"])

    captured = capsys.readouterr()
    assert exc.value.code == 0
    assert "List raw persisted runtime events" in captured.out
    assert "This is not the user-facing transcript" in captured.out
    assert "skiller logs <run_id> --after <sequence>" in captured.out
    assert "status.last_event_sequence" in captured.out


def test_status_command_prints_runtime_summary(
    monkeypatch: pytest.MonkeyPatch,
    fake_container: SimpleNamespace,
    capsys: pytest.CaptureFixture[str],
) -> None:
    controller = _FakeController()
    controller.status_results = [
        {
            "run_id": "run-1",
            "status": "WAITING",
            "wait_type": "input",
            "prompt": "Write a message",
            "last_event_sequence": 42,
            "last_event_type": "RUN_WAITING",
        }
    ]
    _install_runtime(monkeypatch, fake_container, controller)

    exit_code = cli_main.main(["status", "run-1"])

    data, _ = _read_json(capsys)
    assert exit_code == 0
    assert controller.status_calls == [{"run_id": "run-1"}]
    assert data == {
        "run_id": "run-1",
        "status": "WAITING",
        "wait_type": "input",
        "prompt": "Write a message",
        "last_event_sequence": 42,
        "last_event_type": "RUN_WAITING",
    }


def test_runs_command_normalizes_status_filters(
    monkeypatch: pytest.MonkeyPatch,
    fake_container: SimpleNamespace,
    capsys: pytest.CaptureFixture[str],
) -> None:
    controller = _FakeController()
    _install_runtime(monkeypatch, fake_container, controller)

    exit_code = cli_main.main(["runs", "--status", "waiting", "--limit", "5"])

    data, _ = _read_json_list(capsys)
    assert exit_code == 0
    assert controller.list_runs_calls == [(5, ["WAITING"])]
    assert data[0]["id"] == "run-1"


def test_delete_command_delegates_to_runtime_controller(
    monkeypatch: pytest.MonkeyPatch,
    fake_container: SimpleNamespace,
    capsys: pytest.CaptureFixture[str],
) -> None:
    controller = _FakeController()
    _install_runtime(monkeypatch, fake_container, controller)

    exit_code = cli_main.main(["delete", "run-1"])

    data, _ = _read_json(capsys)
    assert exit_code == 0
    assert controller.delete_run_calls == ["run-1"]
    assert data == {"run_id": "run-1", "status": "DELETED", "deleted": True}


def test_action_done_command_marks_runtime_action(
    monkeypatch: pytest.MonkeyPatch,
    fake_container: SimpleNamespace,
    capsys: pytest.CaptureFixture[str],
) -> None:
    controller = _FakeController()
    _install_runtime(monkeypatch, fake_container, controller)

    exit_code = cli_main.main(["action", "done", "run-1", "auth_link"])

    data, _ = _read_json(capsys)
    assert exit_code == 0
    assert controller.action_done_calls == [
        {"run_id": "run-1", "step_id": "auth_link"}
    ]
    assert data == {
        "run_id": "run-1",
        "step_id": "auth_link",
        "status": "DONE",
        "done": True,
        "changed": True,
    }


def test_input_receive_stores_input_and_resumes_matched_runs(
    monkeypatch: pytest.MonkeyPatch,
    fake_container: SimpleNamespace,
    capsys: pytest.CaptureFixture[str],
) -> None:
    controller = _FakeController()
    worker_process_service = _FakeWorkerProcessService()
    _install_runtime(
        monkeypatch,
        fake_container,
        controller,
        worker_process_service=worker_process_service,
    )

    exit_code = cli_main.main(["input", "receive", "run-1", "--text", "database timeout"])

    data, _ = _read_json(capsys)
    assert exit_code == 0
    assert controller.receive_input_calls == [("run-1", "database timeout")]
    assert worker_process_service.calls == [("resume", "run-1")]
    assert data["resumed_runs"] == ["run-1"]


def test_channel_receive_forwards_payload_and_resumes_matched_runs(
    monkeypatch: pytest.MonkeyPatch,
    fake_container: SimpleNamespace,
    capsys: pytest.CaptureFixture[str],
) -> None:
    controller = _FakeController()
    worker_process_service = _FakeWorkerProcessService()
    _install_runtime(
        monkeypatch,
        fake_container,
        controller,
        worker_process_service=worker_process_service,
    )

    exit_code = cli_main.main(
        [
            "channel",
            "receive",
            "whatsapp",
            "172584771580071@lid",
            "--json",
            '{"text":"hola"}',
            "--external-id",
            "msg-1",
            "--dedup-key",
            "dedup-1",
        ]
    )

    data, _ = _read_json(capsys)
    assert exit_code == 0
    assert controller.receive_channel_calls == [
        ("whatsapp", "172584771580071@lid", {"text": "hola"}, "msg-1", "dedup-1")
    ]
    assert worker_process_service.calls == [("resume", "run-1")]
    assert data["resumed_runs"] == ["run-1"]


def test_webhook_receive_forwards_payload_and_resumes_matched_runs(
    monkeypatch: pytest.MonkeyPatch,
    fake_container: SimpleNamespace,
    capsys: pytest.CaptureFixture[str],
) -> None:
    controller = _FakeController()
    worker_process_service = _FakeWorkerProcessService()
    _install_runtime(
        monkeypatch,
        fake_container,
        controller,
        worker_process_service=worker_process_service,
    )

    exit_code = cli_main.main(
        [
            "webhook",
            "receive",
            "github-pr-merged",
            "42",
            "--json",
            '{"ok":true}',
            "--dedup-key",
            "delivery-1",
        ]
    )

    data, _ = _read_json(capsys)
    assert exit_code == 0
    assert controller.receive_webhook_calls == [
        ("github-pr-merged", "42", {"ok": True}, "delivery-1")
    ]
    assert worker_process_service.calls == [("resume", "run-1")]
    assert data["resumed_runs"] == ["run-1"]


def test_webhook_register_forwards_ingress_options_and_prints_url(
    monkeypatch: pytest.MonkeyPatch,
    fake_container: SimpleNamespace,
    capsys: pytest.CaptureFixture[str],
) -> None:
    controller = _FakeController()
    _install_runtime(monkeypatch, fake_container, controller)

    exit_code = cli_main.main(
        [
            "webhook",
            "register",
            "example-auth",
            "--method",
            "GET",
            "--auth",
            "none",
            "--payload-source",
            "query",
        ]
    )

    data, _ = _read_json(capsys)
    assert exit_code == 0
    assert controller.register_webhook_calls == [
        ("example-auth", "GET", "none", "query")
    ]
    assert data["webhook_url"] == "http://127.0.0.1:8001/webhooks/example-auth/{key}"


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["webhook", "list"], {"webhook": "github-ci", "enabled": True}),
        (["webhook", "remove", "github-ci"], {"webhook": "github-ci", "removed": True}),
    ],
)
def test_webhook_list_and_remove_are_controller_passthroughs(
    argv: list[str],
    expected: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
    fake_container: SimpleNamespace,
    capsys: pytest.CaptureFixture[str],
) -> None:
    controller = _FakeController()
    _install_runtime(monkeypatch, fake_container, controller)

    exit_code = cli_main.main(argv)

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    if isinstance(data, list):
        data = data[0]
    assert exit_code == 0
    for key, value in expected.items():
        assert data[key] == value


@pytest.mark.parametrize(
    ("argv", "controller_calls", "expected_status"),
    [
        (
            ["agent", "interrupt", "run-1"],
            "interrupt_agent_calls",
            "ENQUEUED",
        ),
        (
            ["agent", "stats", "run-1", "--agent", "support_agent"],
            "agent_stats_calls",
            "OK",
        ),
    ],
)
def test_agent_commands_delegate_to_runtime_controller(
    argv: list[str],
    controller_calls: str,
    expected_status: str,
    monkeypatch: pytest.MonkeyPatch,
    fake_container: SimpleNamespace,
    capsys: pytest.CaptureFixture[str],
) -> None:
    controller = _FakeController()
    _install_runtime(monkeypatch, fake_container, controller)

    exit_code = cli_main.main(argv)

    data, _ = _read_json(capsys)
    assert exit_code == 0
    assert getattr(controller, controller_calls)
    assert data["status"] == expected_status


def test_agent_model_command_delegates_to_runtime_controller(
    monkeypatch: pytest.MonkeyPatch,
    fake_container: SimpleNamespace,
    capsys: pytest.CaptureFixture[str],
) -> None:
    controller = _FakeController()
    _install_runtime(monkeypatch, fake_container, controller)

    exit_code = cli_main.main(
        [
            "agent",
            "model",
            "run-1",
            "--provider",
            "codex",
            "--model",
            "gpt-5.4",
        ]
    )

    data, _ = _read_json(capsys)
    assert exit_code == 0
    assert controller.agent_model_calls == [
        {
            "run_id": "run-1",
            "provider": "codex",
            "model": "gpt-5.4",
        }
    ]
    assert data == {
        "run_id": "run-1",
        "provider": "codex",
        "model": "gpt-5.4",
        "status": "OK",
        "ok": True,
    }


def _local_process_result() -> SimpleNamespace:
    return SimpleNamespace(
        authenticated=True,
        endpoint="http://127.0.0.1:8001/health",
        home="/virtual/service-home",
        log_path="/virtual/service.log",
        managed=True,
        origin_url="http://127.0.0.1:8001",
        paired=True,
        pid=1234,
        qr_count=1,
        queue_length=2,
        running=False,
        session_path="/virtual/whatsapp/session",
        started=True,
        state="ready",
        stopped=True,
        tunnel_name="skillerwh",
    )


def _local_process_service_class(result: SimpleNamespace):
    class _FakeLocalProcessService:
        calls: list[tuple[str, object]] = []

        def __init__(self, settings: object) -> None:
            self.settings = settings

        def start(self) -> SimpleNamespace:
            self.__class__.calls.append(("start", self.settings))
            return result

        def status(self) -> SimpleNamespace:
            self.__class__.calls.append(("status", self.settings))
            return result

        def stop(self) -> SimpleNamespace:
            self.__class__.calls.append(("stop", self.settings))
            return result

    return _FakeLocalProcessService


@pytest.mark.parametrize(
    ("argv", "service_name", "method", "expected_key"),
    [
        (["server", "start"], "WebhookProcessService", "start", "started"),
        (["server", "status"], "WebhookProcessService", "status", "running"),
        (["server", "stop"], "WebhookProcessService", "stop", "stopped"),
    ],
)
def test_local_process_commands_dispatch_to_selected_service(
    argv: list[str],
    service_name: str,
    method: str,
    expected_key: str,
    monkeypatch: pytest.MonkeyPatch,
    fake_container: SimpleNamespace,
    capsys: pytest.CaptureFixture[str],
) -> None:
    controller = _FakeController()
    _install_runtime(monkeypatch, fake_container, controller)
    service_class = _local_process_service_class(_local_process_result())
    monkeypatch.setattr(cli_main, service_name, service_class)

    exit_code = cli_main.main(argv)

    data, _ = _read_json(capsys)
    assert exit_code == 0
    assert service_class.calls == [(method, fake_container.settings)]
    assert expected_key in data
