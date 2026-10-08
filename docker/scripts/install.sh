#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
command -v docker >/dev/null || { echo 'Instale Docker Engine e Compose Plugin conforme README.' >&2; exit 1; }
docker compose version >/dev/null
[[ -f .env ]] || { cp .env.example .env; chmod 600 .env; echo 'Configure API_DOMAIN e os parâmetros TRAEFIK em docker/.env.' >&2; exit 1; }
if grep -q 'example.com' .env; then echo 'Configure um domínio real antes da instalação.' >&2; exit 1; fi
./scripts/generate-secrets.sh
# Public configuration/SQL must be readable by the container's mysql user,
# even when the package was extracted by root with a restrictive umask.
chmod 644 mariadb/conf.d/server.cnf mariadb/init/001-initial.sql ../database/schema.sql ../database/initial_data.sql
chmod 755 mariadb/init/002-users.sh
compose config --quiet
compose up -d --build --wait --wait-timeout 240
./scripts/check-health.sh
