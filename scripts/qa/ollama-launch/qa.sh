#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "$0")/../../.." && pwd)"
image="skiller-qa-ollama-launch:local"
container="skiller-qa-ollama-launch"
label="run.skiller.qa.ollama-launch"

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
        cp scripts/qa/ollama-launch/Dockerfile "$context/"
        docker build --build-arg "QA_UID=$UID" -t "$image" "$context"
        printf '\nImage ready. Existing QA containers keep their installed version.\n'
        printf 'Use reset, then start to evaluate this build in a clean environment.\n'
        bash "$root/scripts/qa/ollama-launch/qa.sh" start
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
            mkdir -p "$root/scripts/qa/ollama-launch/data/logs"
            docker run -d --name "$container" --label "$label=true" \
                --mount "type=bind,source=$root/scripts/qa/ollama-launch/data,target=/data" \
                "$image" >/dev/null
        fi
        data_source="$(docker inspect --format '{{range .Mounts}}{{if eq .Destination "/data"}}{{.Source}}{{end}}{{end}}' "$container")"
        if [[ "$data_source" != "$root/scripts/qa/ollama-launch/data" ]]; then
            printf 'Outdated QA container: expected the current /data mount.\n' >&2
            printf 'Rebuild the image, then reset and start. Reset deletes internal QA data.\n' >&2
            exit 1
        fi
        docker exec "$container" sh -eu -c '
            test "${SKILLER_RUNTIME_CONFIG_FILE:-}" = /data/config.json
            test "${SKILLER_AGENT_PROVIDERS_FILE:-}" = /data/providers.json
            test -r /data/config.json
            test -r /data/providers.json
            test -r /data/agent.json
            test -r /data/qa/qa.yaml
        ' || {
            printf 'Invalid QA environment: rebuild the image, then reset and start.\n' >&2
            exit 1
        }
        # Bootstrap through the public CLI, without an auth run or a fabricated DB.
        docker exec --workdir /home/tester "$container" skiller runs --limit 1 >/dev/null
        printf 'QA shell: Runtime initialized; QA configuration is mounted in /data.\n'
        printf 'Run skiller @qa to start the agent; do not run auth in this environment.\n'
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
