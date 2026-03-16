from __future__ import annotations

import io
import json
from urllib.error import HTTPError

import pytest

from skiller.infrastructure.llm import minimax_llm
from skiller.infrastructure.llm.minimax_llm import MinimaxLLM

pytestmark = pytest.mark.unit


class _FakeHTTPResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def __enter__(self) -> "_FakeHTTPResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        _ = (exc_type, exc, tb)
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def test_minimax_llm_returns_content_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_urlopen(request, timeout=0):  # noqa: ANN001, ANN202
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return _FakeHTTPResponse(
            {
                "model": "MiniMax-M2.5",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": '{"summary":"ok","severity":"low","next_action":"retry"}',
                        }
                    }
                ],
            }
        )

    monkeypatch.setattr(minimax_llm, "urlopen", fake_urlopen)

    llm = MinimaxLLM(
        api_key="secret-key",
        base_url="https://api.minimax.io/v1",
        model="MiniMax-M2.5",
        timeout_seconds=12.5,
    )
    result = llm.generate([{"role": "user", "content": "Analyze"}])

    assert result == {
        "ok": True,
        "content": '{"summary":"ok","severity":"low","next_action":"retry"}',
        "model": "MiniMax-M2.5",
    }
    assert captured["url"] == "https://api.minimax.io/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer secret-key"
    assert captured["body"] == {
        "model": "MiniMax-M2.5",
        "messages": [{"role": "user", "content": "Analyze"}],
        "reasoning_split": True,
    }
    assert captured["timeout"] == 12.5


def test_minimax_llm_uses_model_override_from_config(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_urlopen(request, timeout=0):  # noqa: ANN001, ANN202
        _ = timeout
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return _FakeHTTPResponse({"choices": [{"message": {"content": "{}"}}]})

    monkeypatch.setattr(minimax_llm, "urlopen", fake_urlopen)

    llm = MinimaxLLM(api_key="secret-key")
    llm.generate(
        [{"role": "user", "content": "Analyze"}], config={"model": "MiniMax-M2.5-highspeed"}
    )

    assert captured["body"]["model"] == "MiniMax-M2.5-highspeed"


def test_minimax_llm_returns_error_when_api_key_missing() -> None:
    llm = MinimaxLLM(api_key="")

    result = llm.generate([{"role": "user", "content": "Analyze"}])

    assert result == {"ok": False, "error": "MiniMax API key is not configured"}


def test_minimax_llm_returns_error_message_from_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request, timeout=0):  # noqa: ANN001, ANN202
        _ = (request, timeout)
        raise HTTPError(
            url="https://api.minimax.io/v1/chat/completions",
            code=401,
            msg="Unauthorized",
            hdrs=None,
            fp=io.BytesIO(b'{"error":{"message":"Invalid API key"}}'),
        )

    monkeypatch.setattr(minimax_llm, "urlopen", fake_urlopen)

    llm = MinimaxLLM(api_key="bad-key")
    result = llm.generate([{"role": "user", "content": "Analyze"}])

    assert result == {"ok": False, "error": "Invalid API key"}


def test_minimax_llm_returns_error_on_invalid_response_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_urlopen(request, timeout=0):  # noqa: ANN001, ANN202
        _ = (request, timeout)
        return _FakeHTTPResponse({"choices": []})

    monkeypatch.setattr(minimax_llm, "urlopen", fake_urlopen)

    llm = MinimaxLLM(api_key="secret-key")
    result = llm.generate([{"role": "user", "content": "Analyze"}])

    assert result == {"ok": False, "error": "MiniMax response missing choices"}
