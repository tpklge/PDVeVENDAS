#!/usr/bin/env bash
set -Eeuo pipefail
TASK_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
python3 "$TASK_ROOT/tools/generate_credentials.py" --root "$TASK_ROOT" "$@"
