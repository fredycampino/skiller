import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AgentSettings:
    loop_max_turns: int
    loop_max_tool_calls: int


def resolve_agent_settings(agent_config_file: str | Path) -> AgentSettings:
    agent_config = _load_agent_config_file(agent_config_file)
    fallback_agent_config = _load_fallback_agent_config()
    runtime_agent_config = _deep_merge_dicts(
        fallback_agent_config,
        _extract_agent_config(agent_config),
    )
    default_max_turns = _require_positive_int_at(
        fallback_agent_config,
        ("loop", "max_turns"),
        "loop.max_turns",
    )
    default_max_tool_calls = _require_positive_int_at(
        fallback_agent_config,
        ("loop", "max_tool_calls"),
        "loop.max_tool_calls",
    )
    return AgentSettings(
        loop_max_turns=_positive_int_setting(
            "AGENT_LOOP_MAX_TURNS",
            runtime_agent_config,
            ("loop", "max_turns"),
            default_max_turns,
        ),
        loop_max_tool_calls=_positive_int_setting(
            "AGENT_LOOP_MAX_TOOL_CALLS",
            runtime_agent_config,
            ("loop", "max_tool_calls"),
            default_max_tool_calls,
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


def _load_fallback_agent_config() -> dict[str, object]:
    fallback_path = Path(__file__).with_name("config.json")
    if not fallback_path.exists():
        raise RuntimeError(f"Missing fallback agent config file: {fallback_path}")
    try:
        payload = json.loads(fallback_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid fallback agent config file: {fallback_path}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"Fallback agent config must be a JSON object: {fallback_path}")
    return payload


def _extract_agent_config(agent_config: dict[str, object]) -> dict[str, object]:
    raw = agent_config.get("agent")
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise RuntimeError("agent.json field 'agent' must be a JSON object")
    return dict(raw)


def _positive_int_setting(
    env_name: str,
    config: dict[str, object],
    path: tuple[str, ...],
    default: int,
) -> int:
    if env_name in os.environ:
        value = os.environ[env_name]
    else:
        config_value = _value_at(config, path)
        value = config_value if config_value is not None else default
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"{env_name} must be a positive integer") from exc
    if parsed <= 0:
        raise RuntimeError(f"{env_name} must be a positive integer")
    return parsed


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


def _require_positive_int_at(
    config: dict[str, object],
    path: tuple[str, ...],
    label: str,
) -> int:
    value = _value_at(config, path)
    if isinstance(value, bool) or not isinstance(value, int):
        raise RuntimeError(f"fallback agent config key '{label}' must be a positive integer")
    if value <= 0:
        raise RuntimeError(f"fallback agent config key '{label}' must be a positive integer")
    return value
