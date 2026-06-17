import json
from collections.abc import Mapping
from pathlib import Path

from skiller.domain.agent.agent_config_model import AgentConfig
from skiller.domain.agent.agent_config_port import (
    AgentConfigPort,
    AgentConfigProviderSource,
    AgentConfigProviderSourceItem,
)
from skiller.domain.agent.agent_config_validation_model import (
    AgentConfigValidation,
    AgentConfigValidationErrorCode,
)
from skiller.domain.agent.agent_llm_provider import AgentLLMProviderType
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

    def list_provider_sources(
        self,
        *,
        config_path: Path | None = None,
    ) -> tuple[AgentConfigProviderSourceItem, ...]:
        explicit_path = self.env.get("AGENT_AGENT_CONFIG_FILE", "").strip()
        if explicit_path:
            return _provider_sources(
                payload=_load_json_object(Path(explicit_path).expanduser()),
                source=AgentConfigProviderSource.ENV,
            )

        global_config_path = self.config_path_global.expanduser()
        global_payload = (
            _load_json_object(global_config_path)
            if global_config_path.exists()
            else {}
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
        local_provider_types = {item.provider_type for item in local_sources}
        global_sources = tuple(
            item
            for item in _provider_sources(
                payload=global_payload,
                source=AgentConfigProviderSource.GLOBAL,
            )
            if item.provider_type not in local_provider_types
        )
        return local_sources + global_sources

    def set_model(
        self,
        *,
        provider_type: AgentLLMProviderType,
        model: str,
        config_path: Path | None = None,
    ) -> None:
        source_by_provider = {
            item.provider_type: item.source
            for item in self.list_provider_sources(config_path=config_path)
        }
        provider_source = source_by_provider.get(provider_type)
        if provider_source is None or provider_source == AgentConfigProviderSource.NONE:
            raise RuntimeError(f"LLM provider is not configured: {provider_type.value}")

        default_path = self._resolve_default_write_path(config_path=config_path)
        provider_path = self._resolve_provider_write_path(
            source=provider_source,
            config_path=config_path,
        )
        if default_path == provider_path:
            payload = _load_json_object(default_path)
            _set_default_provider(payload, provider_type=provider_type)
            _set_provider_model(
                payload,
                provider_type=provider_type,
                model=model,
            )
            _write_json_object(default_path, payload)
            return

        provider_payload = _load_json_object(provider_path)
        _set_provider_model(
            provider_payload,
            provider_type=provider_type,
            model=model,
        )

        default_payload = _load_json_object(default_path)
        _set_default_provider(default_payload, provider_type=provider_type)

        _write_json_object(provider_path, provider_payload)
        _write_json_object(default_path, default_payload)

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
        explicit_path = self.env.get("AGENT_AGENT_CONFIG_FILE", "").strip()
        if explicit_path:
            return Path(explicit_path).expanduser()

        if config_path is not None:
            expanded_config_path = config_path.expanduser()
            if expanded_config_path.exists():
                return expanded_config_path

        return self.config_path_global.expanduser()

    def _resolve_override_config_path(self, *, config_path: Path | None = None) -> Path | None:
        explicit_path = self.env.get("AGENT_AGENT_CONFIG_FILE", "").strip()
        if explicit_path:
            return Path(explicit_path).expanduser()

        if config_path is None:
            return None

        expanded_config_path = config_path.expanduser()
        if expanded_config_path.exists():
            return expanded_config_path
        return None

    def _resolve_default_write_path(self, *, config_path: Path | None = None) -> Path:
        explicit_path = self.env.get("AGENT_AGENT_CONFIG_FILE", "").strip()
        if explicit_path:
            return Path(explicit_path).expanduser()

        override_path = self._resolve_override_config_path(config_path=config_path)
        if override_path is not None:
            return override_path
        return self.config_path_global.expanduser()

    def _resolve_provider_write_path(
        self,
        *,
        source: AgentConfigProviderSource,
        config_path: Path | None = None,
    ) -> Path:
        if source == AgentConfigProviderSource.ENV:
            return self._resolve_config_path(config_path=config_path)
        if source == AgentConfigProviderSource.LOCAL:
            override_path = self._resolve_override_config_path(config_path=config_path)
            if override_path is None:
                raise RuntimeError("Local agent config file not found")
            return override_path
        if source == AgentConfigProviderSource.GLOBAL:
            return self.config_path_global.expanduser()
        raise RuntimeError("LLM provider is not configured")


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


def _set_default_provider(
    payload: dict[str, object],
    *,
    provider_type: AgentLLMProviderType,
) -> None:
    llm = payload.get("llm")
    if not isinstance(llm, dict):
        llm = {}
        payload["llm"] = llm
    llm["default_provider"] = provider_type.value


def _set_provider_model(
    payload: dict[str, object],
    *,
    provider_type: AgentLLMProviderType,
    model: str,
) -> None:
    providers = payload.get("providers")
    if not isinstance(providers, dict):
        raise RuntimeError(f"LLM provider is not configured: {provider_type.value}")

    provider = providers.get(provider_type.value)
    if not isinstance(provider, dict):
        raise RuntimeError(f"LLM provider is not configured: {provider_type.value}")

    provider["model"] = model


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
    providers = payload.get("providers")
    if not isinstance(providers, dict):
        return ()

    items: list[AgentConfigProviderSourceItem] = []
    for provider_id in providers:
        if not isinstance(provider_id, str):
            continue
        try:
            provider_type = AgentLLMProviderType(provider_id)
        except ValueError:
            continue
        items.append(
            AgentConfigProviderSourceItem(
                provider_type=provider_type,
                source=source,
            )
        )
    return tuple(items)
