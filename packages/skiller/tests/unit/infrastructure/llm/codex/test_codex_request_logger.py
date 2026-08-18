import json

import pytest

from skiller.infrastructure.llm.codex.codex_request_logger import (
    CodexFileLLMRequestLogger,
)
from skiller.infrastructure.llm.logger.request_logger import REDACTED_VALUE

pytestmark = pytest.mark.unit


def test_codex_request_logger_redacts_lite_turn_state_and_reasoning(tmp_path) -> None:
    logger = CodexFileLLMRequestLogger(overwrite=True)
    path = tmp_path / "request.json"

    logger.log_request(
        request={
            "extra_headers": {"x-codex-turn-state": "opaque-turn-state"},
            "input": [
                {
                    "type": "reasoning",
                    "encrypted_content": "encrypted-request-reasoning",
                }
            ],
        },
        file=path,
    )
    logger.log_response(
        response={
            "output": [
                {
                    "type": "reasoning",
                    "encrypted_content": "encrypted-response-reasoning",
                }
            ]
        }
    )

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["request"]["extra_headers"]["x-codex-turn-state"] == REDACTED_VALUE
    assert payload["request"]["input"][0]["encrypted_content"] == REDACTED_VALUE
    assert payload["response"]["output"][0]["encrypted_content"] == REDACTED_VALUE
