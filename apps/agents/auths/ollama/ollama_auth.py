#!/usr/bin/env python3
"""Ollama provider setup helper."""

from __future__ import annotations

import argparse
import fcntl
import json
import shutil
import socket
import sys
import urllib.error
import urllib.request
from contextlib import contextmanager
from pathlib import Path

DEFAULT_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_CONTEXT_WINDOW_TOKENS = 32_768
BACKUP_SUFFIX = ".ollama-auth.bak"
MISSING_SUFFIX = ".ollama-auth.missing"


def providers_file() -> Path:
    return Path.home() / ".skiller" / "settings" / "providers.json"


def agent_config_file() -> Path:
    return Path.home() / ".skiller" / "settings" / "agent.json"


def normalize_base_url(base_url: str) -> str:
    normalized = base_url.strip().rstrip("/")
    if not normalized:
        raise ValueError("Ollama base URL is required")
    return normalized.removesuffix("/v1")


def configured_base_url() -> str:
    payload = _read_json_object(providers_file(), missing={})
    providers = payload.get("providers")
    if not isinstance(providers, dict):
        return DEFAULT_BASE_URL
    provider = providers.get("ollama")
    if not isinstance(provider, dict):
        return DEFAULT_BASE_URL
    base_url = provider.get("base_url")
    if not isinstance(base_url, str) or not base_url.strip():
        return DEFAULT_BASE_URL
    return normalize_base_url(base_url)


def discover_models(base_url: str) -> dict[str, object]:
    root = normalize_base_url(base_url)
    installed = _request_json(f"{root}/api/tags", error_message="Invalid Ollama model list")
    active = _request_json(f"{root}/api/ps", error_message="Invalid Ollama active model list")
    contexts = {
        model.get("name"): _positive_int(model.get("context_length"))
        for model in active.get("models", [])
        if isinstance(model, dict)
    }
    models = []
    for entry in installed.get("models", []):
        if not isinstance(entry, dict) or not isinstance(entry.get("name"), str):
            continue
        name = entry["name"]
        details = _request_json(
            f"{root}/api/show",
            error_message="Invalid Ollama model details",
            body={"model": name},
        )
        capabilities = details.get("capabilities", [])
        if "completion" not in capabilities:
            continue
        models.append(
            {
                "model": name,
                "context_window_tokens": contexts.get(name) or DEFAULT_CONTEXT_WINDOW_TOKENS,
            }
        )
    if not models:
        raise ValueError("Ollama returned no available chat models; download one with ollama pull")
    selected = next((m["model"] for m in models if m["model"] in contexts), models[0]["model"])
    return {"base_url": root, "model": selected, "models": models}


def _transaction_directory() -> Path:
    return providers_file().parent / ".ollama-auth-pending"


@contextmanager
def _operation_lock():
    lock_path = providers_file().parent / ".ollama-auth.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def _require_owner(run_id: str) -> None:
    owner_file = _transaction_directory() / "owner"
    if not owner_file.exists():
        raise ValueError("No recoverable Ollama setup owner; preserve pending backups for recovery")
    owner = owner_file.read_text(encoding="utf-8")
    if owner != run_id:
        raise ValueError(f"Ollama setup belongs to run {owner}; only that run may modify it")


def backup_configuration(run_id: str) -> None:
    if not run_id.strip():
        raise ValueError("Ollama setup requires a run ID")
    with _operation_lock():
        directory = _transaction_directory()
        if directory.exists():
            owner_file = directory / "owner"
            owner = owner_file.read_text(encoding="utf-8") if owner_file.exists() else "unknown"
            raise ValueError(
                f"Pending Ollama setup for run {owner}; commit or restore it before retrying"
            )
        # Preserve backups from older helper versions rather than silently replacing them.
        for path in (providers_file(), agent_config_file()):
            if any(
                path.with_name(path.name + suffix).exists()
                for suffix in (BACKUP_SUFFIX, MISSING_SUFFIX)
            ):
                raise ValueError("Existing Ollama backup requires recovery before starting setup")
        directory.mkdir(mode=0o700)
        (directory / "owner").write_text(run_id, encoding="utf-8")
        for path in (providers_file(), agent_config_file()):
            if path.exists():
                shutil.copy2(path, _backup_path(path))
            else:
                _missing_path(path).write_text("missing\n", encoding="utf-8")


def configure(base_url: str, run_id: str) -> dict[str, object]:
    with _operation_lock():
        _require_owner(run_id)
        _require_backups()
        discovered = discover_models(base_url)
        provider_payload = _provider_payload(discovered)
        agent_payload = _agent_payload(str(discovered["model"]))
        try:
            _write_json_object(providers_file(), provider_payload)
            _write_json_object(agent_config_file(), agent_payload)
        except Exception:
            _restore_configuration()
            raise
        return discovered


def commit_configuration(run_id: str) -> None:
    with _operation_lock():
        _require_owner(run_id)
        _require_backups()
        _remove_backups()


def restore_configuration(run_id: str) -> None:
    with _operation_lock():
        _require_owner(run_id)
        _restore_configuration()


def _restore_configuration() -> None:
    for path in (providers_file(), agent_config_file()):
        backup_path = _backup_path(path)
        if backup_path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup_path, path)
        elif _missing_path(path).exists():
            path.unlink(missing_ok=True)
    _remove_backups()


def _provider_payload(discovered: dict[str, object]) -> dict[str, object]:
    payload = _read_json_object(providers_file(), missing={})
    providers = payload.setdefault("providers", {})
    if not isinstance(providers, dict):
        raise ValueError("Provider config providers must contain an object")
    provider = providers.setdefault("ollama", {})
    if not isinstance(provider, dict):
        raise ValueError("Ollama provider config must contain an object")

    provider.pop("model", None)
    for field in (
        "api_key",
        "api_key_env",
        "api_key_file",
        "temperature",
        "top_p",
        "parallel_tool_calls",
        "tool_choice",
        "options",
    ):
        provider.pop(field, None)
    provider.pop("adapter", None)
    provider["base_url"] = discovered["base_url"]
    provider["timeout_seconds"] = 600
    existing = {
        entry["model"]: entry
        for entry in provider.get("models", [])
        if isinstance(entry, dict) and isinstance(entry.get("model"), str)
    }
    provider["models"] = [
        {**existing.get(model["model"], {}), **model} for model in discovered["models"]
    ]
    return payload


def _agent_payload(model: str) -> dict[str, object]:
    payload = _read_json_object(agent_config_file(), missing={})
    llm = payload.setdefault("llm", {})
    if not isinstance(llm, dict):
        raise ValueError("Global agent config llm must contain an object")
    llm["provider"] = "ollama"
    llm["model"] = model
    return payload


def _request_json(
    endpoint: str, *, error_message: str, body: dict[str, object] | None = None
) -> dict[str, object]:
    try:
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(body).encode() if body is not None else None,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise ValueError(f"Ollama returned HTTP {exc.code}") from exc
    except (TimeoutError, socket.timeout) as exc:
        raise ValueError("Ollama connection timed out") from exc
    except urllib.error.URLError as exc:
        raise ValueError(f"Cannot connect to Ollama: {exc.reason}") from exc
    if not isinstance(payload, dict):
        raise ValueError(error_message)
    return payload


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
    return _transaction_directory() / f"{path.name}{BACKUP_SUFFIX}"


def _missing_path(path: Path) -> Path:
    return _transaction_directory() / f"{path.name}{MISSING_SUFFIX}"


def _require_backups() -> None:
    for path in (providers_file(), agent_config_file()):
        if not _backup_path(path).exists() and not _missing_path(path).exists():
            raise ValueError(f"Missing Ollama configuration backup for {path}")


def _remove_backups() -> None:
    for path in (providers_file(), agent_config_file()):
        _backup_path(path).unlink(missing_ok=True)
        _missing_path(path).unlink(missing_ok=True)
    (_transaction_directory() / "owner").unlink()
    _transaction_directory().rmdir()


def main() -> int:
    parser = argparse.ArgumentParser(description="Configure Ollama for Skiller agents.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("base-url")
    probe_parser = subparsers.add_parser("probe")
    probe_parser.add_argument("base_url")
    subparsers.add_parser("backup").add_argument("--run-id", required=True)
    configure_parser = subparsers.add_parser("configure")
    configure_parser.add_argument("base_url")
    configure_parser.add_argument("--run-id", required=True)
    subparsers.add_parser("commit").add_argument("--run-id", required=True)
    subparsers.add_parser("restore").add_argument("--run-id", required=True)
    args = parser.parse_args()

    try:
        if args.command == "base-url":
            print(configured_base_url())
        elif args.command == "probe":
            print(json.dumps(discover_models(args.base_url), sort_keys=True))
        elif args.command == "backup":
            backup_configuration(args.run_id)
            print("backed-up")
        elif args.command == "configure":
            result = configure(args.base_url, args.run_id)
            print(json.dumps(result, sort_keys=True))
        elif args.command == "commit":
            commit_configuration(args.run_id)
            print("committed")
        elif args.command == "restore":
            restore_configuration(args.run_id)
            print("restored")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
