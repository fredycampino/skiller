#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "$0")/../../.." && pwd)"
image="skiller-qa-first-launch:local"
container="skiller-qa-first-launch"
label="run.skiller.qa.first-launch"

usage() {
    printf 'Usage: %s {build|start|reset}\n' "$0"
}

require_owned_container() {
    local owner
    owner="$(docker inspect --format "{{index .Config.Labels \"$label\"}}" "$container")"
    if [[ "$owner" != true ]]; then
        printf 'Refusing to modify container %s: missing QA label.\n' "$container" >&2
        exit 1
    fi
}

case "${1:-}" in
    build)
        context="$(mktemp -d)"
        trap 'rm -rf "$context"' EXIT
        cd "$root"
        uv build --wheel --out-dir "$context"
        cp scripts/qa/first-launch/Dockerfile "$context/"
        docker build -t "$image" "$context"
        printf '\nImage ready. Existing QA containers keep their installed version.\n'
        printf 'Use reset, then start to evaluate this build in a clean environment.\n'
        ;;
    start)
        if [[ ! -t 0 || ! -t 1 ]]; then
            printf 'start requires an interactive terminal.\n' >&2
            exit 1
        fi
        if docker container inspect "$container" >/dev/null 2>&1; then
            require_owned_container
            if [[ "$(docker inspect --format '{{.State.Running}}' "$container")" != true ]]; then
                docker start "$container" >/dev/null
            fi
        else
            docker run -d --name "$container" --label "$label=true" "$image" >/dev/null
        fi
        printf 'QA shell: Skiller is installed with pipx. Run any commands freely.\n'
        printf 'exit leaves the environment intact; reset deletes it, including credentials.\n'
        docker exec -it --workdir /home/tester "$container" bash
        ;;
    reset)
        if docker container inspect "$container" >/dev/null 2>&1; then
            require_owned_container
            docker rm -f "$container" >/dev/null
            printf 'QA environment deleted. The next start creates a clean user home.\n'
        else
            printf 'No QA environment to delete.\n'
        fi
        ;;
    *)
        usage >&2
        exit 1
        ;;
esac
