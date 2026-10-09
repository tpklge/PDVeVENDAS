#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
[[ -z "$(compose ps -q --status running api)" ]] || { echo 'Pare a API antes de renovar a base de sincronização.' >&2; exit 1; }
compose run --rm --no-deps -T --entrypoint python api -c '
from uuid import uuid4
from sqlalchemy import text
from app.db import engine
with engine.begin() as connection:
    result = connection.execute(text("UPDATE catalog_state SET epoch = :epoch WHERE id = 1"), {"epoch": str(uuid4())})
    assert result.rowcount == 1, "Catálogo ausente; execute as migrações primeiro."
print("Base de sincronização renovada. Terminais reconstruirão o catálogo.")
'
