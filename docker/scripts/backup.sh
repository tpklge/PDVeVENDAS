#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
umask 077
mkdir -p backups
chmod 700 backups
TASK_BACKUP="backups/tab5_erp-$(date -u +%Y%m%dT%H%M%SZ).sql.gz"
[[ ! -e "$TASK_BACKUP" ]] || { echo 'Backup já existe.' >&2; exit 1; }
trap 'rm -f "$TASK_BACKUP.tmp"' EXIT
compose exec -T mariadb bash -ec 'umask 077; cfg=$(mktemp); trap "rm -f "$cfg"" EXIT; printf "[client]\nuser=root\npassword=%s\n" "$(cat /run/secrets/db_root_password)" > "$cfg"; mariadb-dump --defaults-extra-file="$cfg" --skip-comments --order-by-primary --skip-add-locks --skip-disable-keys --single-transaction --quick --routines --triggers --databases tab5_erp' | gzip > "$TASK_BACKUP.tmp"
gzip -t "$TASK_BACKUP.tmp"
mv "$TASK_BACKUP.tmp" "$TASK_BACKUP"
echo "Backup protegido por permissões: $TASK_BACKUP"
