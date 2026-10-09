#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
bash scripts/check-health.sh
TASK_EXPECTED_VERSION="$(tr -d '\r\n' < ../VERSION)"
[[ "$TASK_EXPECTED_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]
compose exec -T -e "TAB5_EXPECTED_VERSION=$TASK_EXPECTED_VERSION" api python - <<'PY'
import os
from app.config import VERSION
from app.db import SessionFactory
from app.models import AuthAudit, AuditLog
from sqlalchemy import select, func
assert VERSION == os.environ['TAB5_EXPECTED_VERSION'], 'API ainda desatualizada'
with SessionFactory() as db:
    print('Auditoria de autenticação disponível:', db.scalar(select(func.count()).select_from(AuthAudit)) >= 0)
    print('Auditoria de operações disponível:', db.scalar(select(func.count()).select_from(AuditLog)) >= 0)
print(f'PASS: API {VERSION} e tabelas de auditoria disponíveis; nenhuma credencial exibida.')
PY
TASK_API_CONTAINER="$(compose ps -q api)"
docker inspect "$TASK_API_CONTAINER" --format '{{json .}}' | python3 -c '
import json,sys
container=json.load(sys.stdin)
config=container["HostConfig"]
assert config["ReadonlyRootfs"]
assert "ALL" in config["CapDrop"]
assert any("no-new-privileges" in option for option in config["SecurityOpt"])
assert container["Config"]["User"] == "10001:10001"
assert not config.get("PortBindings")
print("PASS: API sem root, filesystem somente leitura, sem capabilities/portas publicadas.")'
TASK_DOMAIN="$(sed -n 's/^API_DOMAIN=//p' .env | tr -d '\r')"
TASK_DOMAIN="${TASK_DOMAIN:-tab5api.ampere.diadiatech.com.br}"
[[ "$TASK_DOMAIN" =~ ^[a-zA-Z0-9.-]+$ ]]
TASK_HEADERS="$(mktemp)"
trap 'rm -f "$TASK_HEADERS"' EXIT
curl --fail --silent --show-error --connect-timeout 10 --max-time 30 \
    --proto '=https' --tlsv1.2 -D "$TASK_HEADERS" "https://$TASK_DOMAIN/health/ready"
python3 - "$TASK_HEADERS" <<'PY'
from pathlib import Path
import sys
headers=Path(sys.argv[1]).read_text().lower()
assert 'strict-transport-security:' in headers
assert 'max-age=31536000' in headers
assert 'x-content-type-options: nosniff' in headers
assert 'cache-control: no-store' in headers
assert 'x-correlation-id:' in headers
print('\nPASS: HTTPS, certificado, HSTS e cabeçalhos verificados.')
PY
echo 'PASS: revisão do servidor concluída. Testes de concorrência/corrupção são executados em CI isolado.'
