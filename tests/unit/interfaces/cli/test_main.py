from types import SimpleNamespace

import pytest

from skiller.interfaces.cli import main as cli_main


class _FakeController:
    def __init__(self, bootstrap_service, runtime_service, query_service) -> None:  # noqa: ANN001
        self.run_calls: list[tuple[str, dict[str, str], str]] = []
        self.resume_calls: list[str] = []
        self.receive_calls: list[tuple[str, str, dict[str, str], str | None]] = []
        self.logs_calls: list[str] = []
        self.run_result = {"run_id": "run-1", "status": "CREATED"}
        self.logs_result = [{"type": "NOTIFY", "payload": {"step": "done"}}]

    def initialize(self) -> None:
        return None

    def run(self, skill_ref: str, inputs: dict[str, str], *, skill_source: str = "internal") -> dict[str, str]:
        self.run_calls.append((skill_ref, inputs, skill_source))
        return dict(self.run_result)

    def resume(self, run_id: str) -> dict[str, str]:
        self.resume_calls.append(run_id)
        return {"run_id": run_id, "resume_status": "RESUMED", "status": "WAITING"}

    def logs(self, run_id: str) -> list[dict[str, object]]:
        self.logs_calls.append(run_id)
        return list(self.logs_result)

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

    def register_webhook(self, webhook: str) -> dict[str, object]:
        return {
            "webhook": webhook,
            "status": "REGISTERED",
            "secret": "secret-123",
            "enabled": True,
        }

    def remove_webhook(self, webhook: str) -> dict[str, object]:
        return {
            "webhook": webhook,
            "status": "REMOVED",
            "removed": True,
        }


@pytest.fixture
def fake_container() -> SimpleNamespace:
    return SimpleNamespace(
        bootstrap_service=object(),
        runtime_service=object(),
        query_service=object(),
        settings=SimpleNamespace(db_path="/tmp/test.db", webhooks_host="127.0.0.1", webhooks_port=8001),
    )


def test_run_internal_skill_by_name(monkeypatch: pytest.MonkeyPatch, fake_container: SimpleNamespace, capsys: pytest.CaptureFixture[str]) -> None:
    controller = _FakeController(None, None, None)

    monkeypatch.setattr(cli_main, "build_runtime_container", lambda: fake_container)
    monkeypatch.setattr(cli_main, "RuntimeController", lambda **_: controller)

    exit_code = cli_main.main(["run", "notify_test", "--arg", "message=ok"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert controller.run_calls == [("notify_test", {"message": "ok"}, "internal")]
    assert '"run_id": "run-1"' in captured.out


def test_run_external_skill_by_file(monkeypatch: pytest.MonkeyPatch, fake_container: SimpleNamespace, capsys: pytest.CaptureFixture[str]) -> None:
    controller = _FakeController(None, None, None)

    monkeypatch.setattr(cli_main, "build_runtime_container", lambda: fake_container)
    monkeypatch.setattr(cli_main, "RuntimeController", lambda **_: controller)

    exit_code = cli_main.main(["run", "--file", "/tmp/demo.yaml", "--arg", "message=ok"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert controller.run_calls == [("/tmp/demo.yaml", {"message": "ok"}, "file")]
    assert '"status": "CREATED"' in captured.out


def test_run_can_include_logs_in_response(
    monkeypatch: pytest.MonkeyPatch,
    fake_container: SimpleNamespace,
    capsys: pytest.CaptureFixture[str],
) -> None:
    controller = _FakeController(None, None, None)

    monkeypatch.setattr(cli_main, "build_runtime_container", lambda: fake_container)
    monkeypatch.setattr(cli_main, "RuntimeController", lambda **_: controller)

    exit_code = cli_main.main(["run", "notify_test", "--logs"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert controller.logs_calls == ["run-1"]
    assert '"logs": [' in captured.out
    assert '"type": "NOTIFY"' in captured.out


def test_run_can_start_webhooks_when_waiting(
    monkeypatch: pytest.MonkeyPatch,
    fake_container: SimpleNamespace,
    capsys: pytest.CaptureFixture[str],
) -> None:
    controller = _FakeController(None, None, None)
    controller.run_result = {"run_id": "run-1", "status": "WAITING"}

    class _FakeWebhookProcessService:
        def __init__(self, settings) -> None:  # noqa: ANN001
            self.settings = settings

        def start(self):
            return SimpleNamespace(endpoint="http://127.0.0.1:8001/health", pid=1234, started=True)

    monkeypatch.setattr(cli_main, "build_runtime_container", lambda: fake_container)
    monkeypatch.setattr(cli_main, "RuntimeController", lambda **_: controller)
    monkeypatch.setattr(cli_main, "WebhookProcessService", _FakeWebhookProcessService)

    exit_code = cli_main.main(["run", "notify_test", "--start-webhooks"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"status": "WAITING"' in captured.out
    assert '"webhooks_started": true' in captured.out
    assert '"webhooks_pid": 1234' in captured.out


def test_run_fails_when_webhooks_requested_but_process_does_not_start(
    monkeypatch: pytest.MonkeyPatch,
    fake_container: SimpleNamespace,
    capsys: pytest.CaptureFixture[str],
) -> None:
    controller = _FakeController(None, None, None)
    controller.run_result = {"run_id": "run-1", "status": "WAITING"}

    class _FakeWebhookProcessService:
        def __init__(self, settings) -> None:  # noqa: ANN001
            self.settings = settings

        def start(self):
            raise RuntimeError("webhooks process did not become ready")

    monkeypatch.setattr(cli_main, "build_runtime_container", lambda: fake_container)
    monkeypatch.setattr(cli_main, "RuntimeController", lambda **_: controller)
    monkeypatch.setattr(cli_main, "WebhookProcessService", _FakeWebhookProcessService)

    exit_code = cli_main.main(["run", "notify_test", "--start-webhooks"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert '"status": "WAITING"' in captured.out
    assert '"webhooks_started": false' in captured.out
    assert "webhooks process did not become ready" in captured.out


def test_run_failure_with_start_webhooks_can_include_logs(
    monkeypatch: pytest.MonkeyPatch,
    fake_container: SimpleNamespace,
    capsys: pytest.CaptureFixture[str],
) -> None:
    controller = _FakeController(None, None, None)
    controller.run_result = {"run_id": "run-1", "status": "WAITING"}

    class _FakeWebhookProcessService:
        def __init__(self, settings) -> None:  # noqa: ANN001
            self.settings = settings

        def start(self):
            raise RuntimeError("webhooks process did not become ready")

    monkeypatch.setattr(cli_main, "build_runtime_container", lambda: fake_container)
    monkeypatch.setattr(cli_main, "RuntimeController", lambda **_: controller)
    monkeypatch.setattr(cli_main, "WebhookProcessService", _FakeWebhookProcessService)

    exit_code = cli_main.main(["run", "notify_test", "--start-webhooks", "--logs"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert controller.logs_calls == ["run-1"]
    assert '"logs": [' in captured.out


def test_run_rejects_missing_or_duplicated_skill_selection(monkeypatch: pytest.MonkeyPatch, fake_container: SimpleNamespace) -> None:
    monkeypatch.setattr(cli_main, "build_runtime_container", lambda: fake_container)
    monkeypatch.setattr(cli_main, "RuntimeController", _FakeController)

    with pytest.raises(SystemExit) as missing:
        cli_main.main(["run"])
    assert missing.value.code == 2

    with pytest.raises(SystemExit) as duplicated:
        cli_main.main(["run", "notify_test", "--file", "/tmp/demo.yaml"])
    assert duplicated.value.code == 2


def test_resume_run(monkeypatch: pytest.MonkeyPatch, fake_container: SimpleNamespace, capsys: pytest.CaptureFixture[str]) -> None:
    controller = _FakeController(None, None, None)

    monkeypatch.setattr(cli_main, "build_runtime_container", lambda: fake_container)
    monkeypatch.setattr(cli_main, "RuntimeController", lambda **_: controller)

    exit_code = cli_main.main(["resume", "run-123"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert controller.resume_calls == ["run-123"]
    assert '"resume_status": "RESUMED"' in captured.out


def test_webhook_receive_uses_webhook_and_key(
    monkeypatch: pytest.MonkeyPatch,
    fake_container: SimpleNamespace,
    capsys: pytest.CaptureFixture[str],
) -> None:
    controller = _FakeController(None, None, None)

    monkeypatch.setattr(cli_main, "build_runtime_container", lambda: fake_container)
    monkeypatch.setattr(cli_main, "RuntimeController", lambda **_: controller)

    exit_code = cli_main.main(["webhook", "receive", "github-pr-merged", "42", "--json", "{\"ok\":true}"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert controller.receive_calls == [("github-pr-merged", "42", {"ok": True}, None)]
    assert '"accepted": true' in captured.out
    assert '"duplicate": false' in captured.out
    assert '"matched_runs": [' in captured.out


def test_webhook_register(monkeypatch: pytest.MonkeyPatch, fake_container: SimpleNamespace, capsys: pytest.CaptureFixture[str]) -> None:
    controller = _FakeController(None, None, None)

    monkeypatch.setattr(cli_main, "build_runtime_container", lambda: fake_container)
    monkeypatch.setattr(cli_main, "RuntimeController", lambda **_: controller)

    exit_code = cli_main.main(["webhook", "register", "github-ci"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"status": "REGISTERED"' in captured.out
    assert '"secret": "secret-123"' in captured.out
    assert '"webhook_url": "http://127.0.0.1:8001/webhooks/github-ci/{key}"' in captured.out


def test_webhook_remove(monkeypatch: pytest.MonkeyPatch, fake_container: SimpleNamespace, capsys: pytest.CaptureFixture[str]) -> None:
    controller = _FakeController(None, None, None)

    monkeypatch.setattr(cli_main, "build_runtime_container", lambda: fake_container)
    monkeypatch.setattr(cli_main, "RuntimeController", lambda **_: controller)

    exit_code = cli_main.main(["webhook", "remove", "github-ci"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"status": "REMOVED"' in captured.out
    assert '"removed": true' in captured.out
