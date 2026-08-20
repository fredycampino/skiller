#!/usr/bin/env python3
"""Generic OpenAI-compatible provider helper for Skiller onboarding.

Reads the effective provider catalog via `skiller agent providers` and prints
single values so shell steps can capture them. Never prints secrets.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="OpenAI-compatible provider helper for Skiller onboarding."
    )
    parser.add_argument(
        "command",
        choices=["api-key-file", "base-url", "default-model", "timeout-seconds"],
    )
    parser.add_argument("provider")
    args = parser.parse_args()

    provider = find_provider(args.provider)
    if provider is None:
        print(f"unknown provider: {args.provider}", file=sys.stderr)
        return 1

    if args.command == "api-key-file":
        print(api_key_file(provider), end="")
        return 0
    if args.command == "base-url":
        base_url = provider.get("base_url")
        if not isinstance(base_url, str) or not base_url.strip():
            print(f"provider {args.provider} has no base_url", file=sys.stderr)
            return 1
        print(base_url.strip(), end="")
        return 0
    if args.command == "timeout-seconds":
        timeout_seconds = provider.get("timeout_seconds")
        if not isinstance(timeout_seconds, (int, float)) or timeout_seconds <= 0:
            print(f"provider {args.provider} has no timeout_seconds", file=sys.stderr)
            return 1
        print(int(timeout_seconds), end="")
        return 0
    if args.command == "default-model":
        models = provider.get("models")
        if not isinstance(models, list) or not models:
            print(f"provider {args.provider} has no models", file=sys.stderr)
            return 1
        first = models[0]
        if not isinstance(first, dict) or not isinstance(first.get("name"), str):
            print(f"provider {args.provider} has invalid models", file=sys.stderr)
            return 1
        print(first["name"], end="")
        return 0

    print(f"unsupported command: {args.command}", file=sys.stderr)
    return 1


def find_provider(name: str) -> dict | None:
    payload = load_providers_payload()
    if payload is None:
        return None
    providers = payload.get("providers")
    if not isinstance(providers, list):
        return None
    for provider in providers:
        if isinstance(provider, dict) and provider.get("name") == name:
            return provider
    return None


def load_providers_payload() -> dict | None:
    try:
        completed = subprocess.run(
            [skiller_bin(), "agent", "providers"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    try:
        payload = json.loads(completed.stdout)
    except ValueError:
        return None
    if not isinstance(payload, dict) or payload.get("status") != "OK":
        return None
    return payload


def skiller_bin() -> str:
    candidate = Path(sys.prefix) / "bin" / "skiller"
    if candidate.exists():
        return str(candidate)
    return "skiller"


def api_key_file(provider: dict) -> str:
    configured = provider.get("api_key_file")
    if isinstance(configured, str) and configured.strip():
        return str(Path(configured.strip()).expanduser())
    name = provider.get("name")
    return str(Path.home() / ".skiller" / "secrets" / f"{name}_api_key")


if __name__ == "__main__":
    raise SystemExit(main())
