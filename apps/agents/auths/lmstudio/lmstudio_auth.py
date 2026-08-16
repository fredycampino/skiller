#!/usr/bin/env python3
"""LM Studio provider setup helper."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import sys
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_BASE_URL = "http://127.0.0.1:1234/v1"
DEFAULT_CONTEXT_WINDOW_TOKENS = 50_000
LM_API_TOKEN_ENV = "LM_API_TOKEN"
BACKUP_SUFFIX = ".lmstudio-auth.bak"
MISSING_SUFFIX = ".lmstudio-auth.missing"


def providers_file() -> Path:
    return Path.home() / ".skiller" / "settings" / "providers.json"


def agent_config_file() -> Path:
    return Path.home() / ".skiller" / "settings" / "agent.json"


def normalize_base_url(base_url: str) -> str:
    normalized = base_url.strip().rstrip("/")
    if not normalized:
        raise ValueError("LM Studio base URL is required")
    if normalized.endswith("/v1"):
        return normalized
    return f"{normalized}/v1"


def configured_base_url() -> str:
    payload = _read_json_object(providers_file(), missing={})
    providers = payload.get("providers")
    if not isinstance(providers, dict):
        return DEFAULT_BASE_URL
    provider = providers.get("lmstudio")
    if not isinstance(provider, dict):
        return DEFAULT_BASE_URL
    base_url = provider.get("base_url")
    if not isinstance(base_url, str) or not base_url.strip():
        return DEFAULT_BASE_URL
    return normalize_base_url(base_url)


def discover_models(base_url: str) -> dict[str, object]:
    normalized_base_url = normalize_base_url(base_url)
    api_models = _request_json(
        _api_models_endpoint(normalized_base_url),
        error_message="LM Studio /api/v1/models returned an invalid response",
    )
    api_models_by_key = _api_models_by_key(api_models)
    known_context_windows = _configured_context_windows()
    models: list[dict[str, object]] = []
    loaded_model_ids: list[str] = []
    for model_id, api_model in api_models_by_key.items():

        active_context_window = _active_context_window(api_model)
        context_window_tokens = _positive_int(
            active_context_window,
            api_model.get("max_context_length"),
            known_context_windows.get(model_id),
        )
        if context_window_tokens is None:
            context_window_tokens = DEFAULT_CONTEXT_WINDOW_TOKENS

        models.append(
            {
                "model": model_id,
                "context_window_tokens": context_window_tokens,
            }
        )
        if active_context_window is not None:
            loaded_model_ids.append(model_id)

    if not models:
        raise ValueError("LM Studio returned no available models")

    selected_model = loaded_model_ids[0] if loaded_model_ids else models[0]["model"]
    return {
        "base_url": normalized_base_url,
        "model": selected_model,
        "models": models,
    }


def backup_configuration() -> None:
    for path in (providers_file(), agent_config_file()):
        backup_path = _backup_path(path)
        missing_path = _missing_path(path)
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        backup_path.unlink(missing_ok=True)
        missing_path.unlink(missing_ok=True)
        if path.exists():
            shutil.copy2(path, backup_path)
        else:
            missing_path.write_text("missing\n", encoding="utf-8")


def configure(base_url: str) -> dict[str, object]:
    _require_backups()
    discovered = discover_models(base_url)
    provider_payload = _provider_payload(discovered)
    agent_payload = _agent_payload(str(discovered["model"]))
    try:
        _write_json_object(providers_file(), provider_payload)
        _write_json_object(agent_config_file(), agent_payload)
    except Exception:
        restore_configuration()
        raise
    return discovered


def commit_configuration() -> None:
    _remove_backups()


def restore_configuration() -> None:
    for path in (providers_file(), agent_config_file()):
        backup_path = _backup_path(path)
        missing_path = _missing_path(path)
        if backup_path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup_path, path)
        elif missing_path.exists():
            path.unlink(missing_ok=True)
    _remove_backups()


def _provider_payload(discovered: dict[str, object]) -> dict[str, object]:
    payload = _read_json_object(providers_file(), missing={})
    providers = payload.setdefault("providers", {})
    if not isinstance(providers, dict):
        raise ValueError("Provider config providers must contain an object")
    provider = providers.setdefault("lmstudio", {})
    if not isinstance(provider, dict):
        raise ValueError("LM Studio provider config must contain an object")

    provider.pop("model", None)
    api_key_file = provider.get("api_key_file")
    if isinstance(api_key_file, str) and not Path(api_key_file).expanduser().is_file():
        provider.pop("api_key_file")
    provider["base_url"] = discovered["base_url"]
    provider["timeout_seconds"] = 120
    provider["models"] = discovered["models"]
    return payload


def _agent_payload(model: str) -> dict[str, object]:
    payload = _read_json_object(agent_config_file(), missing={})
    llm = payload.setdefault("llm", {})
    if not isinstance(llm, dict):
        raise ValueError("Global agent config llm must contain an object")
    llm["provider"] = "lmstudio"
    llm["model"] = model
    return payload


def _configured_context_windows() -> dict[str, int]:
    payload = _read_json_object(providers_file(), missing={})
    providers = payload.get("providers")
    provider = providers.get("lmstudio") if isinstance(providers, dict) else None
    raw_models = provider.get("models") if isinstance(provider, dict) else None
    if not isinstance(raw_models, list):
        return {}

    context_windows: dict[str, int] = {}
    for raw_model in raw_models:
        if not isinstance(raw_model, dict):
            continue
        model = raw_model.get("model")
        context_window_tokens = _positive_int(raw_model.get("context_window_tokens"))
        if isinstance(model, str) and model.strip() and context_window_tokens is not None:
            context_windows[model.strip()] = context_window_tokens
    return context_windows


def _lmstudio_api_headers() -> dict[str, str]:
    token = os.environ.get(LM_API_TOKEN_ENV, "").strip()
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}


def _request_json(endpoint: str, *, error_message: str) -> dict[str, object]:
    try:
        request = urllib.request.Request(
            endpoint,
            headers=_lmstudio_api_headers(),
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise ValueError(f"LM Studio returned HTTP {exc.code}") from exc
    except (TimeoutError, socket.timeout) as exc:
        raise ValueError("LM Studio connection timed out") from exc
    except urllib.error.URLError as exc:
        raise ValueError(f"Cannot connect to LM Studio: {exc.reason}") from exc
    if not isinstance(payload, dict):
        raise ValueError(error_message)
    return payload


def _api_models_endpoint(base_url: str) -> str:
    base_root = base_url.removesuffix("/v1")
    return f"{base_root}/api/v1/models"


def _api_models_by_key(payload: dict[str, object]) -> dict[str, dict[str, object]]:
    raw_models = payload.get("models")
    if not isinstance(raw_models, list):
        raise ValueError("LM Studio /api/v1/models returned no models")
    models_by_key: dict[str, dict[str, object]] = {}
    for raw_model in raw_models:
        if not isinstance(raw_model, dict) or raw_model.get("type") != "llm":
            continue
        model_key = raw_model.get("key")
        if not isinstance(model_key, str) or not model_key.strip():
            continue
        models_by_key[model_key.strip()] = raw_model
    return models_by_key


def _active_context_window(model: dict[str, object]) -> int | None:
    loaded_instances = model.get("loaded_instances")
    if not isinstance(loaded_instances, list):
        return None
    for instance in loaded_instances:
        if not isinstance(instance, dict):
            continue
        config = instance.get("config")
        if not isinstance(config, dict):
            continue
        context_window = _positive_int(config.get("context_length"))
        if context_window is not None:
            return context_window
    return None


def _positive_int(*values: object) -> int | None:
    for value in values:
        if isinstance(value, bool) or not isinstance(value, int):
            continue
        if value > 0:
            return value
    return None


def _read_json_object(path: Path, *, missing: dict[str, object]) -> dict[str, object]:
    if not path.exists():
        return dict(missing)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Config file must contain a JSON object: {path}")
    return payload


def _write_json_object(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"{json.dumps(payload, indent=2, sort_keys=True)}\n",
        encoding="utf-8",
    )


def _backup_path(path: Path) -> Path:
    return path.with_name(f"{path.name}{BACKUP_SUFFIX}")


def _missing_path(path: Path) -> Path:
    return path.with_name(f"{path.name}{MISSING_SUFFIX}")


def _require_backups() -> None:
    for path in (providers_file(), agent_config_file()):
        if not _backup_path(path).exists() and not _missing_path(path).exists():
            raise ValueError(f"Missing LM Studio configuration backup for {path}")


def _remove_backups() -> None:
    for path in (providers_file(), agent_config_file()):
        _backup_path(path).unlink(missing_ok=True)
        _missing_path(path).unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Configure LM Studio for Skiller agents.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("base-url")
    probe_parser = subparsers.add_parser("probe")
    probe_parser.add_argument("base_url")
    subparsers.add_parser("backup")
    configure_parser = subparsers.add_parser("configure")
    configure_parser.add_argument("base_url")
    subparsers.add_parser("commit")
    subparsers.add_parser("restore")
    args = parser.parse_args()

    try:
        if args.command == "base-url":
            print(configured_base_url())
        elif args.command == "probe":
            print(json.dumps(discover_models(args.base_url), sort_keys=True))
        elif args.command == "backup":
            backup_configuration()
            print("backed-up")
        elif args.command == "configure":
            result = configure(args.base_url)
            print(json.dumps(result, sort_keys=True))
        elif args.command == "commit":
            commit_configuration()
            print("committed")
        elif args.command == "restore":
            restore_configuration()
            print("restored")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
