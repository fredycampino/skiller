import json
from collections.abc import Mapping
from pathlib import Path

from skiller.domain.agent.config.agent_config_port import (
    AgentConfigPort,
    AgentConfigProviderSource,
    AgentConfigProviderSourceItem,
)
from skiller.domain.agent.config.model import AgentConfig
from skiller.domain.agent.config.validation import (
    AgentConfigValidation,
    AgentConfigValidationErrorCode,
)
from skiller.domain.shared.file_reference import resolve_file_reference
from skiller.infrastructure.config.agent_config_mapper import AgentConfigMapper


class JsonAgentConfigPort(AgentConfigPort):
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

    def resolve_config_path(
        self, *, flow_dir: Path, file_reference: str | None
    ) -> Path | None:
        if file_reference is None:
            conventional_path = flow_dir / "agent.json"
            return conventional_path if conventional_path.exists() else None
        path = resolve_file_reference(
            file_reference, environment=self.env, base_dir=flow_dir, home_dir=Path.home()
        )
        if not path.is_file():
            raise FileNotFoundError(f"Missing agent config file: {path}")
        return path

    def get_config(self, *, flow_dir: Path, config_path: Path | None = None) -> AgentConfig:
        payload = self._load_config(config_path=config_path)
        return self.config_mapper.from_json(
            payload,
            tools_base_path=flow_dir,
        )

    def validate_config(
        self, *, flow_dir: Path, config_path: Path | None = None
    ) -> AgentConfigValidation:
        try:
            self.get_config(flow_dir=flow_dir, config_path=config_path)
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

    def list_provider_sources(
        self,
        *,
        config_path: Path | None = None,
    ) -> tuple[AgentConfigProviderSourceItem, ...]:
        global_config_path = self.config_path_global.expanduser()
        global_payload = (
            _load_json_object(global_config_path) if global_config_path.exists() else {}
        )
        local_config_path = self._resolve_override_config_path(config_path=config_path)
        if local_config_path is None:
            return _provider_sources(
                payload=global_payload,
                source=AgentConfigProviderSource.GLOBAL,
            )

        local_payload = _load_json_object(local_config_path)
        local_sources = _provider_sources(
            payload=local_payload,
            source=AgentConfigProviderSource.LOCAL,
        )
        local_providers = {item.provider for item in local_sources}
        global_sources = tuple(
            item
            for item in _provider_sources(
                payload=global_payload,
                source=AgentConfigProviderSource.GLOBAL,
            )
            if item.provider not in local_providers
        )
        return local_sources + global_sources

    def set_model(
        self,
        *,
        provider: str,
        model: str,
        config_path: Path | None = None,
    ) -> None:
        write_path = self._resolve_model_write_path(config_path=config_path)
        payload = _load_json_object(write_path)
        _set_llm_selection(payload, provider=provider, model=model)
        _write_json_object(write_path, payload)

    def _load_config(self, *, config_path: Path | None = None) -> dict[str, object]:
        global_config_path = self.config_path_global.expanduser()
        override_config_path = self._resolve_override_config_path(config_path=config_path)
        if not global_config_path.exists() and override_config_path is None:
            raise FileNotFoundError(
                f"Missing agent config file: {_display_path(global_config_path)}"
            )

        payload: dict[str, object] = {}
        if global_config_path.exists():
            payload = _load_json_object(global_config_path)
        if override_config_path is not None:
            override = _load_json_object(override_config_path)
            return _override_config(payload, override)
        return payload

    def _resolve_config_path(self, *, config_path: Path | None = None) -> Path:
        if config_path is not None:
            return config_path.expanduser()

        return self.config_path_global.expanduser()

    def _resolve_override_config_path(self, *, config_path: Path | None = None) -> Path | None:
        if config_path is None:
            return None

        return config_path.expanduser()

    def _resolve_model_write_path(self, *, config_path: Path | None = None) -> Path:
        override_path = self._resolve_override_config_path(config_path=config_path)
        if override_path is not None and _has_llm_selection(override_path):
            return override_path
        return self.config_path_global.expanduser()


def _validation_error_code(message: str) -> AgentConfigValidationErrorCode:
    if message.startswith("Invalid agent config:"):
        return AgentConfigValidationErrorCode.INVALID_SCHEMA
    if message.startswith("Missing default LLM provider config:"):
        return AgentConfigValidationErrorCode.DEFAULT_PROVIDER_NOT_FOUND
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


def _load_json_object(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Config file must contain a JSON object: {path}")
    return payload


def _write_json_object(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{json.dumps(payload, indent=2)}\n", encoding="utf-8")


def _set_llm_selection(
    payload: dict[str, object],
    *,
    provider: str,
    model: str,
) -> None:
    llm = payload.get("llm")
    if not isinstance(llm, dict):
        llm = {}
        payload["llm"] = llm
    llm["provider"] = provider
    llm["model"] = model


def _has_llm_selection(path: Path) -> bool:
    payload = _load_json_object(path)
    return "llm" in payload


def _override_config(
    base: dict[str, object],
    override: dict[str, object],
) -> dict[str, object]:
    merged = dict(base)
    merged.update(override)
    return merged


def _provider_sources(
    *,
    payload: dict[str, object],
    source: AgentConfigProviderSource,
) -> tuple[AgentConfigProviderSourceItem, ...]:
    llm = payload.get("llm")
    if not isinstance(llm, dict):
        return ()
    provider = llm.get("provider")
    if not isinstance(provider, str) or not provider.strip():
        return ()
    return (
        AgentConfigProviderSourceItem(
            provider=provider.strip(),
            source=source,
        ),
    )
