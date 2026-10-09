#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
[[ $# -eq 2 && "$2" == "--confirm-replace" ]] || { echo 'Uso: restore.sh ARQUIVO.sql.gz --confirm-replace (substitui dados; API deve estar parada)' >&2; exit 1; }
[[ -f "$1" ]]
gzip -t "$1"
compose stop api
# O dump não contém DROP DATABASE: restaurar em banco existente pode reter tabelas
# novas. Consulte o procedimento de restauração em instância vazia no README.
gzip -dc "$1" | compose exec -T mariadb bash -ec 'umask 077; cfg=$(mktemp); trap "rm -f "$cfg"" EXIT; printf "[client]\nuser=root\npassword=%s\n" "$(cat /run/secrets/db_root_password)" > "$cfg"; mariadb --defaults-extra-file="$cfg"'
echo 'Restauração concluída. Execute migrate.sh e invalidate-sync.sh antes de reativar a API em produção.'
