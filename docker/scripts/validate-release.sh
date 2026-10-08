#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
umask 077
TASK_ID="tab5-verify-$(date -u +%Y%m%d%H%M%S)-$$"
TASK_RESTORE="$TASK_ID-restore"
TASK_VOLUME="$TASK_ID-data"
TASK_WORK="$(mktemp -d)"
TASK_MARKER="release-validation-$TASK_ID"
root_sql() {
  compose exec -T mariadb bash -ec 'umask 077; cfg=$(mktemp); trap '\''rm -f "$cfg"'\'' EXIT; printf "[client]\nuser=root\npassword=%s\n" "$(cat /run/secrets/db_root_password)" > "$cfg"; mariadb --defaults-extra-file="$cfg" --batch --skip-column-names tab5_erp'
}
cleanup() {
  docker rm -f "$TASK_RESTORE" >/dev/null 2>&1 || true
  docker volume rm "$TASK_VOLUME" >/dev/null 2>&1 || true
  printf "DELETE FROM app_settings WHERE \`key\`='%s';\n" "$TASK_MARKER" | root_sql >/dev/null 2>&1 || true
  rm -rf "$TASK_WORK"
}
trap cleanup EXIT
./scripts/check-health.sh
printf "INSERT INTO app_settings (\`key\`,value) VALUES ('%s','persisted');\n" "$TASK_MARKER" | root_sql >/dev/null
# Recreate the production containers while retaining their existing volume.
compose up -d --no-deps --force-recreate --wait --wait-timeout 240 mariadb
compose up -d --no-deps --force-recreate --wait --wait-timeout 120 api
TASK_VALUE="$(printf "SELECT value FROM app_settings WHERE \`key\`='%s';\n" "$TASK_MARKER" | root_sql)"
[[ "$TASK_VALUE" == persisted ]] || { echo 'FALHA: persistência.' >&2; exit 1; }
echo 'PASS: persistência após recriação de MariaDB/API.'
./scripts/check-health.sh
./scripts/backup.sh
TASK_BACKUP="$(ls -t backups/tab5_erp-*.sql.gz | head -1)"
gzip -dc "$TASK_BACKUP" > "$TASK_WORK/source.sql"
TASK_IMAGE="$(docker inspect "$(compose ps -q mariadb)" --format '{{.Config.Image}}')"
docker volume create "$TASK_VOLUME" >/dev/null
docker run -d --name "$TASK_RESTORE" --network none \
  --mount "type=volume,src=$TASK_VOLUME,dst=/var/lib/mysql" \
  --mount "type=bind,src=$TASK_DOCKER_DIR/secrets/db_root_password,dst=/run/secrets/db_root_password,readonly" \
  -e MARIADB_ROOT_PASSWORD_FILE=/run/secrets/db_root_password "$TASK_IMAGE" >/dev/null
TASK_READY=false
for ((attempt=0; attempt<120; attempt++)); do
  if docker exec "$TASK_RESTORE" healthcheck.sh --connect --innodb_initialized >/dev/null 2>&1; then TASK_READY=true; break; fi
  sleep 2
done
[[ "$TASK_READY" == true ]] || { docker logs --tail=40 "$TASK_RESTORE"; exit 1; }
docker exec -i "$TASK_RESTORE" bash -ec 'umask 077; cfg=$(mktemp); trap '\''rm -f "$cfg"'\'' EXIT; printf "[client]\nuser=root\npassword=%s\n" "$(cat /run/secrets/db_root_password)" > "$cfg"; mariadb --defaults-extra-file="$cfg"' < "$TASK_WORK/source.sql"
docker exec "$TASK_RESTORE" bash -ec 'umask 077; cfg=$(mktemp); trap '\''rm -f "$cfg"'\'' EXIT; printf "[client]\nuser=root\npassword=%s\n" "$(cat /run/secrets/db_root_password)" > "$cfg"; mariadb-dump --defaults-extra-file="$cfg" --skip-comments --order-by-primary --skip-add-locks --skip-disable-keys --single-transaction --quick --routines --triggers --databases tab5_erp' > "$TASK_WORK/restored.sql"
cmp "$TASK_WORK/source.sql" "$TASK_WORK/restored.sql" >/dev/null || { echo 'FALHA: dump restaurado difere do backup.' >&2; exit 1; }
echo 'PASS: backup restaurado em MariaDB isolado; schema e dados idênticos.'
[[ -z "$(docker port "$TASK_RESTORE")" ]]
./scripts/check-health.sh
if [[ "${SKIP_PUBLIC_HTTPS:-0}" != 1 ]]; then
  TASK_DOMAIN="$(compose config --format json | python3 -c 'import json,sys,re; d=json.load(sys.stdin); print(re.search(r"Host\(`([^`]+)`\)",d["services"]["api"]["labels"]["traefik.http.routers.tab5-api.rule"]).group(1))')"
  curl --fail --show-error "https://$TASK_DOMAIN/health/ready"
  echo
  echo 'PASS: HTTPS verificado e API pronta.'
fi
echo 'PASS: validação da infraestrutura concluída.'
