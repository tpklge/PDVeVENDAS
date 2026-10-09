#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
# Incremental update: existing schema/data/secrets and microSD formats are retained.
bash scripts/update-security.sh
bash scripts/validate-security.sh
echo 'TAB5 ERP atualizado e validado; instale o BIN OTA da mesma versão no Tab5.'
