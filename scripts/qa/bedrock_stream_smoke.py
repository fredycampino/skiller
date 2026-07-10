#!/usr/bin/env python3
"""Bedrock streaming vs non-streaming permission smoke test (no credential output).

Purpose
-------
Diagnoses a subtle IAM situation where a role is granted
``bedrock:InvokeModelWithResponseStream`` (streaming) but NOT
``bedrock:InvokeModel`` (non-streaming). In that case the streaming API
(``converse_stream``) succeeds while the non-streaming API (``converse``)
returns ``AccessDeniedException`` for the exact same model and resource.

This is exactly how Claude Code keeps working through a profile whose role
only allows the streaming action, while plain ``converse``/``invoke_model``
calls fail.

What it does
------------
1. Calls ``converse_stream`` -> action ``bedrock:InvokeModelWithResponseStream``.
2. Calls ``converse``        -> action ``bedrock:InvokeModel``.
Then reports ALLOWED/DENIED for each so you can see which actions the current
role grants.

Notes
-----
- No credentials, tokens, or secret values are printed.
- Some newer models (for example ``us.anthropic.claude-sonnet-5``) reject the
  ``temperature`` parameter, so it is intentionally omitted.
- Model IDs are typically inference profile IDs (``us.anthropic...``).
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare Bedrock streaming vs non-streaming authorization for a role."
    )
    parser.add_argument(
        "--region",
        default=os.getenv("AWS_REGION"),
        help="AWS region (default: AWS_REGION or profile config region)",
    )
    parser.add_argument(
        "--model-id",
        default=os.getenv("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-5"),
        help=(
            "Bedrock model ID/profile "
            "(default: BEDROCK_MODEL_ID or us.anthropic.claude-sonnet-5)"
        ),
    )
    parser.add_argument(
        "--profile",
        default=os.getenv("AWS_PROFILE", "aternitybedrock"),
        help="AWS profile name (default: AWS_PROFILE or aternitybedrock)",
    )
    return parser.parse_args()


def _stream_text(response: dict[str, Any]) -> str:
    parts: list[str] = []
    for event in response.get("stream", []):
        delta = event.get("contentBlockDelta", {}).get("delta", {})
        text = delta.get("text")
        if isinstance(text, str):
            parts.append(text)
    return "".join(parts).strip()


def _extract_text(response: dict[str, Any]) -> str:
    content = response.get("output", {}).get("message", {}).get("content", [])
    parts: list[str] = []
    for block in content:
        text = block.get("text")
        if isinstance(text, str):
            parts.append(text)
    return "\n".join(parts).strip()


def main() -> int:
    args = _parse_args()

    try:
        import boto3
        from botocore.exceptions import BotoCoreError, ClientError
    except Exception:
        print(
            "ERROR: boto3/botocore is not installed. Install with: pip install boto3",
            file=sys.stderr,
        )
        return 2

    session_kwargs: dict[str, str] = {}
    if args.profile:
        session_kwargs["profile_name"] = args.profile
    client_kwargs: dict[str, str] = {}
    if args.region:
        client_kwargs["region_name"] = args.region

    session = boto3.Session(**session_kwargs)
    client = session.client("bedrock-runtime", **client_kwargs)

    messages = [{"role": "user", "content": [{"text": "Responde exactamente: PONG"}]}]
    inference_config = {"maxTokens": 10}

    region_label = args.region or "(resolved by AWS profile/config)"
    print(f"profile={args.profile} region={region_label} model_id={args.model_id}")

    stream_ok = False
    invoke_ok = False

    # 1) STREAMING -> bedrock:InvokeModelWithResponseStream
    print("\n=== converse_stream (streaming / bedrock:InvokeModelWithResponseStream) ===")
    try:
        response = client.converse_stream(
            modelId=args.model_id,
            messages=messages,
            inferenceConfig=inference_config,
        )
        text = _stream_text(response) or "(empty response)"
        print(f"RESULT: ALLOWED (200) response_text={text}")
        stream_ok = True
    except (ClientError, BotoCoreError) as exc:
        print(f"RESULT: DENIED_OR_ERROR: {exc}", file=sys.stderr)

    # 2) NON-STREAM -> bedrock:InvokeModel
    print("\n=== converse (non-stream / bedrock:InvokeModel) ===")
    try:
        response = client.converse(
            modelId=args.model_id,
            messages=messages,
            inferenceConfig=inference_config,
        )
        text = _extract_text(response) or "(empty response)"
        print(f"RESULT: ALLOWED (200) response_text={text}")
        invoke_ok = True
    except (ClientError, BotoCoreError) as exc:
        print(f"RESULT: DENIED_OR_ERROR: {exc}", file=sys.stderr)

    print("\n=== summary ===")
    print(f"InvokeModelWithResponseStream={'ALLOWED' if stream_ok else 'DENIED'}")
    print(f"InvokeModel={'ALLOWED' if invoke_ok else 'DENIED'}")
    if stream_ok and not invoke_ok:
        print(
            "DIAGNOSIS: role grants streaming only. Add bedrock:InvokeModel for parity, "
            "or use the streaming API (converse_stream)."
        )

    # Exit 0 only when at least the streaming path works (the primary check).
    return 0 if stream_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
