#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
bash scripts/backup.sh
compose build api
compose stop api
compose run --rm --no-deps -T migrate
compose up -d --no-deps --force-recreate --wait --wait-timeout 240 api
bash scripts/check-health.sh
echo 'Sincronização incremental disponível; dados e credenciais preservados.'
