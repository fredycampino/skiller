#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../../.."
: "${AGENT_MINIMAX_API_KEY:?Set AGENT_MINIMAX_API_KEY before running this test}"
export AGENT_MINIMAX_API_KEY
context="$(mktemp -d)"
trap 'rm -rf "$context"' EXIT
uv build --wheel --out-dir "$context"
cp packages/skiller/tests/e2e-install/{Dockerfile,check.sh} "$context/"
image="skiller-e2e-first-install:local"
docker build -t "$image" "$context"
docker run --rm --env AGENT_MINIMAX_API_KEY "$image"
