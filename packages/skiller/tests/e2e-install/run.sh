#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../../.."
: "${SKILLER_MINIMAX_API_KEY:?Set SKILLER_MINIMAX_API_KEY before running this test}"
export SKILLER_MINIMAX_API_KEY
context="$(mktemp -d)"
trap 'rm -rf "$context"' EXIT
uv build --wheel --out-dir "$context"
cp packages/skiller/tests/e2e-install/{Dockerfile,check.sh} "$context/"
image="skiller-e2e-first-install:local"
docker build -t "$image" "$context"
docker run --rm --env SKILLER_MINIMAX_API_KEY "$image"
