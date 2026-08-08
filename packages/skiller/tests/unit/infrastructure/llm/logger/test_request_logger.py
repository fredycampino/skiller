import json
import re

import pytest

from skiller.infrastructure.llm.logger.request_logger import (
    REDACTED_VALUE,
    FileLLMRequestLogger,
    redact_keys,
    to_log_value,
)

pytestmark = pytest.mark.unit


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


def test_file_llm_request_logger_writes_one_file_per_request(tmp_path) -> None:
    logger = FileLLMRequestLogger()
    file = tmp_path / "llm.json"

    logger.log_request(request={"message": "first"}, file=file)
    logger.log_request(request={"message": "second"}, file=file)
    logger.log_request(request={"message": "third"}, file=file)
    logger.log_response(response={"content": "done"})

    paths = sorted(tmp_path.glob("*.json"))
    assert len(paths) == 3
    assert all(re.fullmatch(r"llm-\d{8}-\d{6}-\d{3}(?:-\d{3})?\.json", path.name) for path in paths)
    assert logger.current_path is not None
    assert _read_json(logger.current_path) == {
        "sequence": 3,
        "request": {"message": "third"},
        "response": {"content": "done"},
        "error": None,
    }


def test_file_llm_request_logger_overwrite_reuses_single_file(tmp_path) -> None:
    logger = FileLLMRequestLogger(overwrite=True)
    file = tmp_path / "llm.json"

    logger.log_request(request={"message": "first"}, file=file)
    logger.log_response(response={"content": "first-done"})
    logger.log_request(request={"message": "second"}, file=file)
    logger.log_response(response={"content": "second-done"})

    assert [path.name for path in tmp_path.glob("*.json")] == ["llm.json"]
    assert _read_json(file) == {
        "sequence": 2,
        "request": {"message": "second"},
        "response": {"content": "second-done"},
        "error": None,
    }


def test_file_llm_request_logger_uses_provider_redaction_hooks(tmp_path) -> None:
    logger = FakeRedactingFileLLMRequestLogger()
    file = tmp_path / "llm.json"

    logger.log_request(
        request={
            "api_key": "secret",
            "headers": {
                "Authorization": "Bearer token",
            },
            "messages": ["hello"],
        },
        file=file,
    )
    logger.log_response(
        response={
            "content": "done",
            "metadata": {
                "access_token": "token",
            },
        },
    )

    paths = list(tmp_path.glob("*.json"))
    assert len(paths) == 1
    payload = _read_json(paths[0])

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
    _ = tmp_path
    logger = FileLLMRequestLogger()

    with pytest.raises(RuntimeError, match="requires a request log"):
        logger.log_response(response={"content": "done"})


def _read_json(path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))
