from skiller.infrastructure.llm.codex.codex_turn_session import CODEX_TURN_STATE_HEADER
from skiller.infrastructure.llm.logger.request_logger import (
    FileLLMRequestLogger,
    redact_keys,
    to_log_value,
)


class CodexFileLLMRequestLogger(FileLLMRequestLogger):
    def redact_request(self, *, request: object) -> object:
        return _redact_codex_state(request)

    def redact_response(self, *, response: object) -> object:
        return _redact_codex_state(response)


def _redact_codex_state(value: object) -> object:
    log_value = to_log_value(value)
    return redact_keys(
        log_value,
        keys={CODEX_TURN_STATE_HEADER, "encrypted_content"},
    )
