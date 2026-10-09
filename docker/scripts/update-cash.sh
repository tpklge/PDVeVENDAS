#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
# Back up existing commercial data before the additive 006_cash migration.
bash scripts/backup.sh
compose build api
compose stop api
compose run --rm --no-deps -T migrate
compose up -d --no-deps --force-recreate --wait --wait-timeout 240 api
bash scripts/check-health.sh
echo 'Caixa/financeiro: migração e API prontas. Dados e credenciais preservados.'
echo 'Instale o OTA 0.9.0 e abra o caixa antes de concluir novas vendas.'
