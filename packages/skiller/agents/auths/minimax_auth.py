#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any


def main() -> int:
    parser = argparse.ArgumentParser(
        description="MiniMax credential helper for Skiller onboarding."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("api-key-file", help="Print the resolved API key file path.")

    args = parser.parse_args()
    if args.command == "api-key-file":
        print(default_api_key_file())
        return 0

    raise RuntimeError(f"unsupported command: {args.command}")


def default_api_key_file() -> Path:
    configured_path = configured_api_key_file()
    if configured_path is not None:
        return configured_path
    return Path.home() / ".skiller" / "secrets" / "minimax_api_key"


def configured_api_key_file() -> Path | None:
    config_path = Path(
        os.environ.get(
            "AGENT_AGENT_CONFIG_FILE",
            Path.home() / ".skiller" / "settings" / "agent.json",
        )
    ).expanduser()
    if not config_path.exists():
        return None

    try:
        config = read_json(config_path)
    except (OSError, ValueError):
        return None

    providers = config.get("providers")
    if not isinstance(providers, dict):
        return None

    minimax = providers.get("minimax")
    if not isinstance(minimax, dict):
        return None

    api_key_file = minimax.get("api_key_file")
    if not isinstance(api_key_file, str) or not api_key_file.strip():
        return None

    return Path(api_key_file).expanduser()


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"file must contain a JSON object: {path}")
    return payload


if __name__ == "__main__":
    raise SystemExit(main())
