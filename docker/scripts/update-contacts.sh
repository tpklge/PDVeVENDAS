#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
# Preserve the running database before additive migration 003_contacts.
bash scripts/backup.sh
compose build api
compose stop api
compose run --rm --no-deps -T migrate
compose up -d --no-deps --force-recreate --wait --wait-timeout 240 api
bash scripts/check-health.sh
echo 'Clientes e fornecedores: migração e API prontas. Usuários, produtos e senhas preservados.'
