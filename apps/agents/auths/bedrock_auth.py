#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

VERIFY_MARKER = "skiller-bedrock-auth-ok"
DEFAULT_MODEL = "us.anthropic.claude-opus-4-6-v1"


class AuthError(Exception):
    pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Bedrock auth helper for Skiller onboarding.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("configured-profile", help="Print configured Bedrock profile if present.")
    verify_parser = subparsers.add_parser("verify", help="Verify Bedrock profile credentials.")
    verify_parser.add_argument("--profile", required=True)
    verify_parser.add_argument(
        "--model",
        default=os.environ.get("SKILLER_BEDROCK_MODEL", DEFAULT_MODEL),
    )

    args = parser.parse_args()
    try:
        if args.command == "configured-profile":
            configured_profile = _configured_profile()
            if configured_profile is None:
                raise AuthError("bedrock profile is not configured")
            print(configured_profile)
            return 0
        if args.command == "verify":
            _verify(profile=args.profile, model=args.model)
            return 0
        raise AuthError(f"unsupported command: {args.command}")
    except AuthError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def _verify(*, profile: str, model: str) -> None:
    profile = profile.strip()
    if not profile:
        raise AuthError("profile is required")
    model = model.strip()
    if not model:
        raise AuthError("model is required")
    text = _verify_with_boto3(profile=profile, model=model)
    if text is None:
        text = _verify_with_aws_cli(profile=profile, model=model)
    if VERIFY_MARKER not in text:
        raise AuthError("bedrock verification did not return expected marker")
    print(f"{VERIFY_MARKER} ({model}, profile={profile})")


def _verify_with_boto3(*, profile: str, model: str) -> str | None:
    try:
        import boto3
        from botocore.config import Config
        from botocore.exceptions import BotoCoreError, ClientError
    except Exception:  # noqa: BLE001
        return None

    try:
        session = boto3.Session(profile_name=profile)
        client = session.client("bedrock-runtime", config=Config(read_timeout=60))
        response = client.converse(
            modelId=model,
            messages=[
                {
                    "role": "user",
                    "content": [{"text": f"Reply with exactly: {VERIFY_MARKER}"}],
                }
            ],
            inferenceConfig={"maxTokens": 20, "temperature": 0},
        )
    except (ClientError, BotoCoreError) as exc:
        raise AuthError(f"bedrock verification failed: {exc}") from exc
    return _extract_text_from_converse_response(response)


def _verify_with_aws_cli(*, profile: str, model: str) -> str:
    payload = {
        "messages": [
            {
                "role": "user",
                "content": [{"text": f"Reply with exactly: {VERIFY_MARKER}"}],
            }
        ],
        "inferenceConfig": {"maxTokens": 20, "temperature": 0},
    }
    command = [
        "aws",
        "bedrock-runtime",
        "converse",
        "--profile",
        profile,
        "--model-id",
        model,
        "--output",
        "json",
        "--cli-binary-format",
        "raw-in-base64-out",
        "--cli-input-json",
        json.dumps(payload),
    ]
    try:
        result = subprocess.run(  # noqa: S603
            command,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise AuthError(f"failed to execute aws cli: {exc}") from exc
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        stdout = (result.stdout or "").strip()
        detail = stderr or stdout or f"exit code {result.returncode}"
        raise AuthError(f"bedrock verification failed: {detail}")
    try:
        response = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise AuthError(f"invalid aws cli response: {exc}") from exc
    if not isinstance(response, dict):
        raise AuthError("invalid aws cli response payload")
    return _extract_text_from_converse_response(response)


def _extract_text_from_converse_response(response: dict[str, Any]) -> str:
    output = response.get("output")
    if not isinstance(output, dict):
        raise AuthError("bedrock response missing output")
    message = output.get("message")
    if not isinstance(message, dict):
        raise AuthError("bedrock response missing message")
    content = message.get("content")
    if not isinstance(content, list):
        raise AuthError("bedrock response missing content")
    return "".join(
        block.get("text", "")
        for block in content
        if isinstance(block, dict) and isinstance(block.get("text"), str)
    ).strip()


def _configured_profile() -> str | None:
    config_path = Path(
        os.environ.get(
            "AGENT_AGENT_CONFIG_FILE",
            Path.home() / ".skiller" / "settings" / "agent.json",
        )
    ).expanduser()
    if not config_path.exists():
        return None
    config = _read_json(config_path)
    providers = config.get("providers")
    if not isinstance(providers, dict):
        return None
    bedrock = providers.get("bedrock")
    if not isinstance(bedrock, dict):
        return None
    profile = bedrock.get("profile")
    if not isinstance(profile, str) or not profile.strip():
        return None
    return profile.strip()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AuthError(f"failed to read config: {exc}") from exc
    if not isinstance(payload, dict):
        raise AuthError(f"config must contain a JSON object: {path}")
    return payload


if __name__ == "__main__":
    raise SystemExit(main())
