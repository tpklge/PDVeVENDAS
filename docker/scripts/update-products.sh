#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
# Back up the running database before additive migration 002. Do not erase volumes.
bash scripts/backup.sh
compose build api
compose stop api
compose run --rm --no-deps -T migrate
compose up -d --no-deps --force-recreate --wait --wait-timeout 240 api
bash scripts/check-health.sh
echo 'Produtos: API e migração disponíveis. Usuários e dados anteriores preservados.'
