import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

FLOW_DIR = Path(__file__).resolve().parents[1] / "auths/codex"


def run_auth(home, *args, model=""):
    return subprocess.run(
        [sys.executable, str(FLOW_DIR / "codex_auth.py"), *args],
        env={**os.environ, "HOME": str(home), "SKILLER_OPENAI_CODEX_MODEL": model},
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize("model,expected", [("", "gpt-5.6-luna"), ("custom-model", "custom-model")])
def test_prepare_selection_uses_flow_model(tmp_path, model, expected):
    result = run_auth(tmp_path, "prepare-verify-config", model=model)
    assert result.returncode == 0, result.stderr
    assert result.stdout == expected
    selection = json.loads((tmp_path / ".skiller/settings/agent.tmp.json").read_text())
    assert selection == {"llm": {"provider": "codex", "model": expected}}


@pytest.mark.parametrize("credentials,expected", [(None, "missing"), ({}, "missing"),
    ({"access_token": "test", "account_id": "account"}, "ready")])
def test_initial_check_only_requires_local_credentials(tmp_path, credentials, expected):
    credentials_path = tmp_path / ".skiller/secrets/openai-codex.json"
    if credentials is not None:
        credentials_path.parent.mkdir(parents=True)
        credentials_path.write_text(json.dumps(credentials))
    flow = yaml.safe_load((FLOW_DIR / "codex.yaml").read_text())
    command = flow["steps"][0]["command"]
    command = command.replace("{{runtime.python}}", sys.executable)
    command = command.replace("{{flow.dir}}", str(FLOW_DIR))
    # Even an unsupported model cannot trigger remote verification in this step.
    result = subprocess.run(
        ["sh", "-c", command],
        env={**os.environ, "HOME": str(tmp_path), "SKILLER_OPENAI_CODEX_MODEL": "unsupported"},
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == expected


def test_stream_error_preserves_provider_diagnostic(monkeypatch):
    import io
    import runpy
    import urllib.request

    auth = runpy.run_path(str(FLOW_DIR / "codex_auth.py"))
    event = {"type": "error", "message": "model is not supported"}
    stream = io.BytesIO(f"data: {json.dumps(event)}\n".encode())
    monkeypatch.setattr(urllib.request, "urlopen", lambda *args, **kwargs: stream)
    with pytest.raises(auth["AuthError"], match="model is not supported"):
        auth["post_codex_stream"](
            access_token="test", account_id="account", payload={"model": "unsupported"}
        )
