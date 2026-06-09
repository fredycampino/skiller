#!/usr/bin/env bash
set -euo pipefail

image="${SKILLER_ANDROID_SIM_IMAGE:-skiller-android-sim}"
engine="${SKILLER_CONTAINER_ENGINE:-docker}"
fixture_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

build_args=()
if [ -n "${SKILLER_PACKAGE:-}" ]; then
  build_args+=(--build-arg "SKILLER_PACKAGE=${SKILLER_PACKAGE}")
fi

"${engine}" build \
  "${build_args[@]}" \
  -f "${fixture_dir}/Dockerfile" \
  -t "${image}" \
  "${fixture_dir}"

if [ "$#" -eq 0 ]; then
  exec "${engine}" run --rm -it "${image}"
fi

if [ -t 0 ] && [ -t 1 ]; then
  exec "${engine}" run --rm -it "${image}" "$@"
fi

exec "${engine}" run --rm "${image}" "$@"
