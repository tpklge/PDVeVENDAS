"""Bounded incremental catalog with a commit revision and explicit stale cursors."""
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select
from .dependencies import Db
from .models import Product
from .products import Read, lock_catalog, serialize

router = APIRouter(prefix="/api/v1/sync", tags=["synchronization"])


@router.get("/products")
def products(user: Read, db: Db, since: int = Query(0, ge=0),
             after_id: int = Query(0, ge=0), limit: int = Query(2, ge=1, le=25),
             revision: int | None = Query(None, ge=1),
             epoch: str | None = Query(None, min_length=36, max_length=36)):
    state = lock_catalog(db)
    if since > state.revision or (epoch is not None and epoch != state.epoch) or (since and epoch is None):
        raise HTTPException(409, "Base do cache mudou. Faça atualização completa.")
    if after_id and (revision is None or epoch is None):
        raise HTTPException(422, "Página seguinte exige revisão da primeira página.")
    if revision is not None and revision != state.revision:
        raise HTTPException(409, "Catálogo mudou. Cache preservado; reinicie a atualização.")
    rows = db.scalars(select(Product).where(Product.id > after_id,
        Product.sync_revision > since).order_by(Product.id).limit(limit + 1)).unique().all()
    return {"format": 2, "epoch": state.epoch, "revision": state.revision,
            "since": since, "items": [serialize(row) for row in rows[:limit]],
            "next_id": rows[limit - 1].id if len(rows) > limit else None,
            "complete": len(rows) <= limit}
