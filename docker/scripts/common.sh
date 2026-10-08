#!/usr/bin/env bash
set -Eeuo pipefail
TASK_DOCKER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$TASK_DOCKER_DIR"
compose() { docker compose --env-file .env -f compose.yaml "$@"; }
