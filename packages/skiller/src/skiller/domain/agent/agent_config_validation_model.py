from dataclasses import dataclass
from enum import Enum


class AgentConfigValidationErrorCode(str, Enum):
    CONFIG_NOT_FOUND = "CONFIG_NOT_FOUND"
    INVALID_JSON = "INVALID_JSON"
    INVALID_SCHEMA = "INVALID_SCHEMA"
    DEFAULT_PROVIDER_NOT_FOUND = "DEFAULT_PROVIDER_NOT_FOUND"
    PROVIDER_CLIENT_TYPE_UNSUPPORTED = "PROVIDER_CLIENT_TYPE_UNSUPPORTED"
    PROVIDER_MODEL_UNSUPPORTED = "PROVIDER_MODEL_UNSUPPORTED"
    API_KEY_MISSING = "API_KEY_MISSING"
    API_KEY_ENV_MISSING = "API_KEY_ENV_MISSING"
    API_KEY_FILE_MISSING = "API_KEY_FILE_MISSING"
    ENV_OVERRIDE_INVALID = "ENV_OVERRIDE_INVALID"


@dataclass(frozen=True)
class AgentConfigValidation:
    ok: bool
    error: AgentConfigValidationErrorCode | None = None
    message: str = ""

    @classmethod
    def valid(cls) -> "AgentConfigValidation":
        return cls(ok=True)

    @classmethod
    def invalid(
        cls,
        *,
        error: AgentConfigValidationErrorCode,
        message: str,
    ) -> "AgentConfigValidation":
        return cls(
            ok=False,
            error=error,
            message=message,
        )
