#!/usr/bin/env python3
"""Minimal Bedrock connectivity smoke test (no credential output).

Model ID notes for this account/profile:
- Anthropic models in this account are enabled primarily via INFERENCE_PROFILE.
- For Claude Opus/Sonnet/Haiku modern families, use inference profile IDs like:
  - us.anthropic.claude-opus-4-6-v1
  - global.anthropic.claude-opus-4-6-v1
- Using the base foundation model ID (for example
  anthropic.claude-opus-4-6-v1) may fail with a validation error indicating
  that on-demand throughput is not supported for direct model invocation.
- If invocation fails with "use inference profile", switch modelId to the
  profile ID/ARN returned by:
  aws bedrock list-inference-profiles --region <region> --profile <profile>
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Send a minimal hello-world request to AWS Bedrock Converse API."
    )
    parser.add_argument(
        "--region",
        default=os.getenv("AWS_REGION"),
        help="AWS region (default: AWS_REGION or profile config region)",
    )
    parser.add_argument(
        "--model-id",
        default=os.getenv("BEDROCK_MODEL_ID", "us.anthropic.claude-opus-4-6-v1"),
        help="Bedrock model ID/profile (default: BEDROCK_MODEL_ID or us.anthropic.claude-opus-4-6-v1)",
    )
    parser.add_argument(
        "--profile",
        default=os.getenv("AWS_PROFILE", "claude-bedrock"),
        help="AWS profile name (default: AWS_PROFILE or claude-bedrock)",
    )
    return parser.parse_args()


def _extract_text(response: dict[str, Any]) -> str:
    content = (
        response.get("output", {})
        .get("message", {})
        .get("content", [])
    )
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
        print("ERROR: boto3/botocore is not installed. Install with: pip install boto3", file=sys.stderr)
        return 2

    session_kwargs: dict[str, str] = {}
    if args.profile:
        session_kwargs["profile_name"] = args.profile

    try:
        session = boto3.Session(**session_kwargs)
        client_kwargs: dict[str, str] = {}
        if args.region:
            client_kwargs["region_name"] = args.region
        client = session.client("bedrock-runtime", **client_kwargs)
        response = client.converse(
            modelId=args.model_id,
            messages=[
                {
                    "role": "user",
                    "content": [{"text": "Hola mundo. Responde solo: OK"}],
                }
            ],
            inferenceConfig={"maxTokens": 20, "temperature": 0},
        )
    except (ClientError, BotoCoreError) as exc:
        # Intentionally avoid printing environment or secret values.
        print(f"BEDROCK_CONNECTIVITY_FAILED: {exc}", file=sys.stderr)
        return 1

    text = _extract_text(response) or "(empty response)"
    usage = response.get("usage", {})
    input_tokens = usage.get("inputTokens")
    output_tokens = usage.get("outputTokens")
    total_tokens = usage.get("totalTokens")

    print("BEDROCK_CONNECTIVITY_OK")
    print(f"model_id={args.model_id}")
    print(f"region={args.region or '(resolved by AWS profile/config)'}")
    print(f"response_text={text}")
    print(
        "usage_input_tokens="
        f"{input_tokens} usage_output_tokens={output_tokens} usage_total_tokens={total_tokens}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
