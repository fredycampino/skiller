import json
from collections.abc import Mapping
from pathlib import Path

from skiller.domain.agent.agent_config_model import AgentConfig
from skiller.domain.agent.agent_config_port import AgentConfigPort
from skiller.domain.agent.agent_config_validation_model import (
    AgentConfigValidation,
    AgentConfigValidationErrorCode,
)
from skiller.infrastructure.config.agent_config_adapter import agent_config_from_json


class JsonAgentConfigProvider(AgentConfigPort):
    def __init__(
        self,
        *,
        config_path: Path,
        env: Mapping[str, str],
    ) -> None:
        self.config_path = config_path
        self.env = env

    def get_config(self) -> AgentConfig:
        return agent_config_from_json(
            self._load_config(),
            env=self.env,
        )

    def validate_config(self) -> AgentConfigValidation:
        try:
            self.get_config()
        except FileNotFoundError as exc:
            return AgentConfigValidation.invalid(
                error=AgentConfigValidationErrorCode.CONFIG_NOT_FOUND,
                message=str(exc),
            )
        except json.JSONDecodeError as exc:
            return AgentConfigValidation.invalid(
                error=AgentConfigValidationErrorCode.INVALID_JSON,
                message=(
                    f"Invalid JSON config file: {_display_path(self.config_path)} "
                    f"(line {exc.lineno}, column {exc.colno})"
                ),
            )
        except ValueError as exc:
            return AgentConfigValidation.invalid(
                error=_validation_error_code(str(exc)),
                message=str(exc),
            )

        return AgentConfigValidation.valid()

    def _load_config(self) -> dict[str, object]:
        config_path = self.config_path.expanduser()
        if not config_path.exists():
            raise FileNotFoundError(f"Missing agent config file: {_display_path(config_path)}")
        try:
            payload = json.loads(config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            raise
        if not isinstance(payload, dict):
            raise ValueError(f"Config file must contain a JSON object: {config_path}")
        return payload


def _validation_error_code(message: str) -> AgentConfigValidationErrorCode:
    if message.startswith("Invalid agent config:"):
        return AgentConfigValidationErrorCode.INVALID_SCHEMA
    if message.startswith("Missing default LLM provider config:"):
        return AgentConfigValidationErrorCode.DEFAULT_PROVIDER_NOT_FOUND
    if message.startswith("Unsupported client_type="):
        return AgentConfigValidationErrorCode.PROVIDER_CLIENT_TYPE_UNSUPPORTED
    if message.startswith("Unsupported model="):
        return AgentConfigValidationErrorCode.PROVIDER_MODEL_UNSUPPORTED
    if message.startswith("Missing environment variable for api_key_env:"):
        return AgentConfigValidationErrorCode.API_KEY_ENV_MISSING
    if message.startswith("LLM provider requires api_key"):
        return AgentConfigValidationErrorCode.API_KEY_MISSING
    if message.startswith("Missing api_key_file:"):
        return AgentConfigValidationErrorCode.API_KEY_FILE_MISSING
    if " must be " in message:
        return AgentConfigValidationErrorCode.ENV_OVERRIDE_INVALID
    return AgentConfigValidationErrorCode.INVALID_SCHEMA


def _display_path(path: Path) -> str:
    expanded = path.expanduser()
    home = Path.home()
    try:
        relative = expanded.relative_to(home)
        return f"~/{relative}"
    except ValueError:
        return str(expanded)
