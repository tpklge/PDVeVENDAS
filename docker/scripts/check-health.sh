#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
compose exec -T api python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=5); print('API e schema disponíveis')"
# Falha se MariaDB possuir qualquer porta publicada.
TASK_CONTAINER="$(compose ps -q mariadb)"
[[ -n "$TASK_CONTAINER" ]]
docker inspect "$TASK_CONTAINER" --format '{{json .HostConfig.PortBindings}}' | python3 -c 'import json,sys; assert not json.load(sys.stdin), "MariaDB com porta publicada"'
