import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ShellSettings:
    allowlist_enabled: bool
    workspace: str
    allow_env_prefix: bool
    allowed_commands: tuple[str, ...]
    sandbox_enabled: bool


def resolve_shell_settings(agent_config_file: str | Path) -> ShellSettings:
    agent_config = _load_agent_config_file(agent_config_file)
    fallback_shell_config = _load_fallback_shell_config()
    shell_config = _deep_merge_dicts(
        fallback_shell_config,
        _extract_shell_config(agent_config),
    )
    default_allowlist_enabled = _require_bool_at(
        fallback_shell_config,
        ("policy", "allowlist", "enabled"),
        "policy.allowlist.enabled",
    )
    default_workspace = _require_string_at(
        fallback_shell_config,
        ("policy", "allowlist", "workspace"),
        "policy.allowlist.workspace",
    )
    default_allow_env_prefix = _require_bool_at(
        fallback_shell_config,
        ("policy", "allowlist", "allow_env_prefix"),
        "policy.allowlist.allow_env_prefix",
    )
    default_allowed_commands = _require_string_list_at(
        fallback_shell_config,
        ("policy", "allowlist", "allowed_commands"),
        "policy.allowlist.allowed_commands",
    )
    default_sandbox_enabled = _require_bool_at(
        fallback_shell_config,
        ("policy", "sandbox", "enabled"),
        "policy.sandbox.enabled",
    )

    return ShellSettings(
        allowlist_enabled=_bool_setting(
            "AGENT_SHELL_ALLOWLIST_ENABLED",
            shell_config,
            ("policy", "allowlist", "enabled"),
            default_allowlist_enabled,
        ),
        workspace=_path_setting(
            "AGENT_SHELL_ALLOWLIST_WORKSPACE",
            shell_config,
            ("policy", "allowlist", "workspace"),
            default_workspace,
        ),
        allow_env_prefix=_bool_setting(
            "AGENT_SHELL_ALLOWLIST_ALLOW_ENV_PREFIX",
            shell_config,
            ("policy", "allowlist", "allow_env_prefix"),
            default_allow_env_prefix,
        ),
        allowed_commands=tuple(
            _string_list_setting(
                "AGENT_SHELL_ALLOWLIST_ALLOWED_COMMANDS",
                shell_config,
                ("policy", "allowlist", "allowed_commands"),
                default_allowed_commands,
            )
        ),
        sandbox_enabled=_bool_setting(
            "AGENT_SHELL_SANDBOX_ENABLED",
            shell_config,
            ("policy", "sandbox", "enabled"),
            default_sandbox_enabled,
        ),
    )


def _load_agent_config_file(agent_config_file: str | Path) -> dict[str, object]:
    config_path = Path(agent_config_file).expanduser()
    if not config_path.exists():
        return {}
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        display_path = _display_path(config_path)
        raise RuntimeError(
            f"Invalid JSON config file: {display_path} "
            f"(line {exc.lineno}, column {exc.colno})"
        ) from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"Config file must contain a JSON object: {config_path}")
    return payload


def _load_fallback_shell_config() -> dict[str, object]:
    fallback_path = Path(__file__).with_name("config.json")
    if not fallback_path.exists():
        raise RuntimeError(f"Missing fallback shell config file: {fallback_path}")
    try:
        payload = json.loads(fallback_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid fallback shell config file: {fallback_path}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"Fallback shell config must be a JSON object: {fallback_path}")
    return payload


def _extract_shell_config(agent_config: dict[str, object]) -> dict[str, object]:
    raw = agent_config.get("shell")
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise RuntimeError("agent.json field 'shell' must be a JSON object")
    return dict(raw)


def _setting(
    env_name: str,
    config: dict[str, object],
    path: tuple[str, ...],
    default: object,
) -> object:
    if env_name in os.environ:
        return os.environ[env_name]
    value = _value_at(config, path)
    if value is not None:
        return value
    return default


def _string_setting(
    env_name: str,
    config: dict[str, object],
    path: tuple[str, ...],
    default: str,
) -> str:
    return str(_setting(env_name, config, path, default)).strip()


def _path_setting(
    env_name: str,
    config: dict[str, object],
    path: tuple[str, ...],
    default: str,
) -> str:
    value = _string_setting(env_name, config, path, default)
    if value.startswith("~"):
        return str(Path(value).expanduser())
    return value


def _string_list_setting(
    env_name: str,
    config: dict[str, object],
    path: tuple[str, ...],
    default: list[str],
) -> list[str]:
    if env_name in os.environ:
        raw = os.environ[env_name]
        if not isinstance(raw, str):
            raise RuntimeError(f"{env_name} must be a comma-separated string")
        return [item.strip() for item in raw.split(",") if item.strip()]

    value = _value_at(config, path)
    if value is None:
        return list(default)
    if not isinstance(value, list):
        raise RuntimeError(f"{env_name} must be a list of strings")

    parsed: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise RuntimeError(f"{env_name} must be a list of non-empty strings")
        parsed.append(item.strip())
    return parsed


def _bool_setting(
    env_name: str,
    config: dict[str, object],
    path: tuple[str, ...],
    default: bool,
) -> bool:
    value = _setting(env_name, config, path, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    if isinstance(value, (int, float)):
        return bool(value)
    raise RuntimeError(f"{env_name} must be a boolean")


def _value_at(config: dict[str, object], path: tuple[str, ...]) -> object | None:
    value: object = config
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def _deep_merge_dicts(left: dict[str, object], right: dict[str, object]) -> dict[str, object]:
    merged: dict[str, object] = dict(left)
    for key, right_value in right.items():
        left_value = merged.get(key)
        if isinstance(left_value, dict) and isinstance(right_value, dict):
            merged[key] = _deep_merge_dicts(left_value, right_value)
            continue
        merged[key] = right_value
    return merged


def _display_path(path: Path) -> str:
    expanded = path.expanduser()
    home = Path.home()
    try:
        relative = expanded.relative_to(home)
        return f"~/{relative}"
    except ValueError:
        return str(expanded)


def _require_bool_at(
    config: dict[str, object],
    path: tuple[str, ...],
    label: str,
) -> bool:
    value = _value_at(config, path)
    if value is None:
        raise RuntimeError(f"fallback shell config is missing required key: {label}")
    if isinstance(value, bool):
        return value
    raise RuntimeError(f"fallback shell config key '{label}' must be a boolean")


def _require_string_at(
    config: dict[str, object],
    path: tuple[str, ...],
    label: str,
) -> str:
    value = _value_at(config, path)
    if value is None:
        raise RuntimeError(f"fallback shell config is missing required key: {label}")
    if not isinstance(value, str):
        raise RuntimeError(f"fallback shell config key '{label}' must be a string")
    return value


def _require_string_list_at(
    config: dict[str, object],
    path: tuple[str, ...],
    label: str,
) -> list[str]:
    value = _value_at(config, path)
    if value is None:
        raise RuntimeError(f"fallback shell config is missing required key: {label}")
    if not isinstance(value, list):
        raise RuntimeError(f"fallback shell config key '{label}' must be a list of strings")
    parsed: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise RuntimeError(f"fallback shell config key '{label}' must be a list of strings")
        stripped = item.strip()
        if not stripped:
            raise RuntimeError(
                f"fallback shell config key '{label}' must be a list of non-empty strings"
            )
        parsed.append(stripped)
    return parsed
