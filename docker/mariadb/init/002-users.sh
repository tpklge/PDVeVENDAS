#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
app_password="$(cat /run/secrets/db_app_password)"
migration_password="$(cat /run/secrets/db_migration_password)"
[[ "$app_password" =~ ^[A-Za-z0-9_-]{32,}$ ]] || exit 1
[[ "$migration_password" =~ ^[A-Za-z0-9_-]{32,}$ ]] || exit 1
TASK_CONFIG="$(mktemp)"
trap 'rm -f "$TASK_CONFIG"' EXIT
printf '[client]\nuser=root\npassword=%s\n' "$(cat /run/secrets/db_root_password)" > "$TASK_CONFIG"
# Executable entrypoint hook: call the socket client directly, without relying
# on shell functions that the official entrypoint does not export.
mariadb --defaults-extra-file="$TASK_CONFIG" --protocol=socket <<SQL
CREATE USER IF NOT EXISTS 'tab5_app'@'%' IDENTIFIED BY '$app_password';
GRANT SELECT, INSERT, UPDATE, DELETE ON tab5_erp.* TO 'tab5_app'@'%';
CREATE USER IF NOT EXISTS 'tab5_migrator'@'%' IDENTIFIED BY '$migration_password';
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, DROP, INDEX, REFERENCES ON tab5_erp.* TO 'tab5_migrator'@'%';
SQL
unset app_password migration_password
