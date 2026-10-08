#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
command -v docker >/dev/null || { echo 'Instale Docker Engine e Compose Plugin conforme README.' >&2; exit 1; }
docker compose version >/dev/null
[[ -f .env ]] || { cp .env.example .env; chmod 600 .env; echo 'Configure API_DOMAIN e ACME_EMAIL em docker/.env.' >&2; exit 1; }
if grep -q 'example.com' .env; then echo 'Configure um domínio real antes da instalação.' >&2; exit 1; fi
./scripts/generate-secrets.sh
compose config --quiet
compose up -d --build
./scripts/check-health.sh
