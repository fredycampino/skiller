import json
from dataclasses import dataclass

import pytest

from skiller.infrastructure.llm.logger.request_logger import (
    REDACTED_VALUE,
    FileLLMRequestLogger,
    redact_keys,
    to_log_value,
)

pytestmark = pytest.mark.unit


@dataclass(frozen=True)
class ExampleRequest:
    model: str
    api_key: str


class FakeRedactingFileLLMRequestLogger(FileLLMRequestLogger):
    def redact_request(
        self,
        *,
        request: object,
    ) -> object:
        payload = to_log_value(request)
        return redact_keys(
            payload,
            keys={"api_key", "authorization"},
        )

    def redact_response(
        self,
        *,
        response: object,
    ) -> object:
        payload = to_log_value(response)
        return redact_keys(
            payload,
            keys={"access_token"},
        )


def test_file_llm_request_logger_writes_request_and_response(tmp_path) -> None:
    logger = FileLLMRequestLogger(directory=tmp_path)

    logger.log_request(request=ExampleRequest(model="gpt-test", api_key="secret"))
    logger.log_response(response={"content": "done"})

    payload = _read_json(tmp_path / "0001.json")

    assert payload == {
        "sequence": 1,
        "request": {
            "model": "gpt-test",
            "api_key": "secret",
        },
        "response": {
            "content": "done",
        },
        "error": None,
    }


def test_file_llm_request_logger_writes_one_file_per_request(tmp_path) -> None:
    logger = FileLLMRequestLogger(directory=tmp_path)

    logger.log_request(request={"message": "first"})
    logger.log_request(request={"message": "second"})
    logger.log_request(request={"message": "third"})
    logger.log_response(response={"content": "done"})

    assert sorted(path.name for path in tmp_path.glob("*.json")) == [
        "0001.json",
        "0002.json",
        "0003.json",
    ]
    assert _read_json(tmp_path / "0001.json") == {
        "sequence": 1,
        "request": {"message": "first"},
        "response": None,
        "error": None,
    }
    assert _read_json(tmp_path / "0002.json") == {
        "sequence": 2,
        "request": {"message": "second"},
        "response": None,
        "error": None,
    }
    assert _read_json(tmp_path / "0003.json") == {
        "sequence": 3,
        "request": {"message": "third"},
        "response": {"content": "done"},
        "error": None,
    }


def test_file_llm_request_logger_uses_provider_redaction_hooks(tmp_path) -> None:
    logger = FakeRedactingFileLLMRequestLogger(directory=tmp_path)

    logger.log_request(
        request={
            "api_key": "secret",
            "headers": {
                "Authorization": "Bearer token",
            },
            "messages": ["hello"],
        },
    )
    logger.log_response(
        response={
            "content": "done",
            "metadata": {
                "access_token": "token",
            },
        },
    )

    payload = _read_json(tmp_path / "0001.json")

    assert payload["request"] == {
        "api_key": REDACTED_VALUE,
        "headers": {
            "Authorization": REDACTED_VALUE,
        },
        "messages": ["hello"],
    }
    assert payload["response"] == {
        "content": "done",
        "metadata": {
            "access_token": REDACTED_VALUE,
        },
    }


def test_file_llm_request_logger_requires_request_before_response(tmp_path) -> None:
    logger = FileLLMRequestLogger(directory=tmp_path)

    with pytest.raises(RuntimeError, match="requires a request log"):
        logger.log_response(response={"content": "done"})


def _read_json(path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))
