#!/usr/bin/env python3
"""One-shot Claude Agent SDK smoke test against Amazon Bedrock (no credential output).

Goal
----
Prove that the *Claude Agent SDK* (not a hand-rolled CLI call) works in one-shot
mode against Bedrock using the current AWS role. Because the role grants only
``bedrock:InvokeModelWithResponseStream`` (streaming) and denies
``bedrock:InvokeModel`` (non-streaming), a successful answer here is itself proof
that the SDK used the streaming transport: a non-streaming call would fail with
AccessDeniedException.

Requirements
------------
- ``claude-agent-sdk`` installed (``pip install claude-agent-sdk``).
- The ``claude`` CLI available on PATH (the SDK orchestrates it under the hood).
- Bedrock env: CLAUDE_CODE_USE_BEDROCK=1, AWS_PROFILE, AWS_REGION.

No credentials, tokens, or secrets are printed.
"""

from __future__ import annotations

import asyncio
import os
import sys

MODEL = os.environ.get("AGENT_BEDROCK_MODEL", "us.anthropic.claude-sonnet-5")
PROFILE = os.environ.get("AWS_PROFILE", "aternitybedrock")
REGION = os.environ.get("AWS_REGION", "us-east-1")


async def _run() -> int:
    try:
        from claude_agent_sdk import (
            AssistantMessage,
            ClaudeAgentOptions,
            ResultMessage,
            TextBlock,
            query,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: claude-agent-sdk not importable: {exc}", file=sys.stderr)
        return 2

    options = ClaudeAgentOptions(
        model=MODEL,
        max_turns=1,
        env={
            "CLAUDE_CODE_USE_BEDROCK": "1",
            "AWS_PROFILE": PROFILE,
            "AWS_REGION": REGION,
        },
    )

    print(f"sdk=claude-agent-sdk mode=one-shot profile={PROFILE} region={REGION} model={MODEL}")

    answer_parts: list[str] = []
    got_result = False
    try:
        async for message in query(prompt="Responde exactamente: PONG", options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        answer_parts.append(block.text)
            elif isinstance(message, ResultMessage):
                got_result = True
    except Exception as exc:  # noqa: BLE001
        print(f"RESULT: FAILED -> {exc}", file=sys.stderr)
        return 1

    answer = "".join(answer_parts).strip()
    if answer or got_result:
        print(f"RESULT: OK (one-shot via SDK) response_text={answer or '(empty)'}")
        print(
            "PROOF: a real answer with a streaming-only role means the SDK used "
            "InvokeModelWithResponseStream (non-streaming would be AccessDenied)."
        )
        return 0

    print("RESULT: NO_ANSWER (no assistant text and no result message)", file=sys.stderr)
    return 1


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
