from __future__ import annotations

import json
import subprocess

import pytest

from skiller.tools.webhooks import launcher


def test_receive_webhook_invokes_runtime_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    recorded: dict[str, object] = {}

    def fake_run(cmd, **kwargs):  # noqa: ANN001
        recorded["cmd"] = cmd
        recorded["kwargs"] = kwargs
        return subprocess.CompletedProcess(
            cmd,
            0,
            stdout=json.dumps({"accepted": True, "duplicate": False, "matched_runs": ["run-1"]}),
            stderr="",
        )

    monkeypatch.setattr(launcher.subprocess, "run", fake_run)

    result = launcher.receive_webhook("test", "42", {"ok": True}, dedup_key="delivery-1")

    assert result["matched_runs"] == ["run-1"]
    assert recorded["cmd"] == [
        launcher.sys.executable,
        "-m",
        "skiller",
        "webhook",
        "receive",
        "test",
        "42",
        "--json",
        '{"ok":true}',
        "--dedup-key",
        "delivery-1",
    ]


def test_receive_webhook_raises_when_command_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(cmd, **kwargs):  # noqa: ANN001
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="boom")

    monkeypatch.setattr(launcher.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="boom"):
        launcher.receive_webhook("test", "42", {"ok": True})
