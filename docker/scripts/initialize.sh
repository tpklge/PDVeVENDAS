#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
# Provisionamento explícito no servidor. A API nunca recebe a senha SQL root.
[[ -f secrets/api_admin_password ]] || { echo 'Gere as credenciais primeiro.' >&2; exit 1; }
compose run --rm -T -v "$TASK_DOCKER_DIR/secrets/api_admin_password:/run/provision/admin_password:ro" api python -m app.cli provision-admin --password-file /run/provision/admin_password
