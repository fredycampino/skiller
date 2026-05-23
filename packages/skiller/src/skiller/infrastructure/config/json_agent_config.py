import json
from collections.abc import Mapping
from pathlib import Path

from skiller.domain.agent.agent_config_model import AgentConfig
from skiller.domain.agent.agent_config_port import AgentConfigPort
from skiller.domain.agent.agent_config_validation_model import (
    AgentConfigValidation,
    AgentConfigValidationErrorCode,
)
from skiller.infrastructure.config.agent_config_mapper import AgentConfigMapper


class JsonAgentConfig(AgentConfigPort):
    def __init__(
        self,
        *,
        config_path_global: Path,
        config_mapper: AgentConfigMapper,
        env: Mapping[str, str],
    ) -> None:
        self.config_path_global = config_path_global
        self.config_mapper = config_mapper
        self.env = env

    def get_config(self, *, config_path: Path | None = None) -> AgentConfig:
        return self.config_mapper.from_json(self._load_config(config_path=config_path))

    def validate_config(self, *, config_path: Path | None = None) -> AgentConfigValidation:
        try:
            self.get_config(config_path=config_path)
        except FileNotFoundError as exc:
            return AgentConfigValidation.invalid(
                error=AgentConfigValidationErrorCode.CONFIG_NOT_FOUND,
                message=str(exc),
            )
        except json.JSONDecodeError as exc:
            resolved_config_path = self._resolve_config_path(config_path=config_path)
            return AgentConfigValidation.invalid(
                error=AgentConfigValidationErrorCode.INVALID_JSON,
                message=(
                    f"Invalid JSON config file: {_display_path(resolved_config_path)} "
                    f"(line {exc.lineno}, column {exc.colno})"
                ),
            )
        except ValueError as exc:
            return AgentConfigValidation.invalid(
                error=_validation_error_code(str(exc)),
                message=str(exc),
            )

        return AgentConfigValidation.valid()

    def _load_config(self, *, config_path: Path | None = None) -> dict[str, object]:
        resolved_config_path = self._resolve_config_path(config_path=config_path)
        if not resolved_config_path.exists():
            raise FileNotFoundError(
                f"Missing agent config file: {_display_path(resolved_config_path)}"
            )
        try:
            payload = json.loads(resolved_config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            raise
        if not isinstance(payload, dict):
            raise ValueError(f"Config file must contain a JSON object: {resolved_config_path}")
        return payload

    def _resolve_config_path(self, *, config_path: Path | None = None) -> Path:
        explicit_path = self.env.get("AGENT_AGENT_CONFIG_FILE", "").strip()
        if explicit_path:
            return Path(explicit_path).expanduser()

        if config_path is not None:
            expanded_config_path = config_path.expanduser()
            if expanded_config_path.exists():
                return expanded_config_path

        return self.config_path_global.expanduser()


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
    if message.startswith("Tool '") or message.startswith("Unknown agent tool config:"):
        return AgentConfigValidationErrorCode.INVALID_SCHEMA
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
