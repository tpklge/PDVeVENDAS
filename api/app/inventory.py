"""Exact, authorized stock mutations with durable retry results and audit trail."""
import hashlib
import json
from decimal import Decimal
from typing import Annotated, Literal
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import Field, field_validator, model_validator
from sqlalchemy import select, or_
from .dependencies import Db, Input, Current, allowed
from .models import Product, StockMovement, InventoryRequest, User, utcnow
from .products import lock_catalog, record

router = APIRouter(prefix='/api/v1/inventory', tags=['inventory'])
Read = Annotated[User, Depends(allowed('inventory.read'))]
Adjust = Annotated[User, Depends(allowed('inventory.adjust'))]
Quantity = Annotated[Decimal, Field(ge=0, max_digits=15, decimal_places=3)]


class Adjustment(Input):
    product_id: int = Field(ge=1)
    product_version: int = Field(ge=1)
    kind: Literal['entry', 'exit', 'adjustment']
    quantity: Quantity | None = None
    target_quantity: Quantity | None = None
    reason: str = Field(min_length=3, max_length=240)
    idempotency_key: str = Field(min_length=16, max_length=64, pattern=r'^[A-Za-z0-9_-]+$')

    @field_validator('reason')
    @classmethod
    def clean_reason(cls, value):
        value = value.strip()
        if len(value) < 3 or any(ord(c) < 32 for c in value):
            raise ValueError('Informe justificativa válida')
        return value

    @model_validator(mode='after')
    def operation_quantity(self):
        if self.kind == 'adjustment':
            if self.target_quantity is None or self.quantity is not None:
                raise ValueError('Ajuste exige saldo contado, sem quantidade de entrada/saída')
        elif self.quantity is None or self.quantity <= 0 or self.target_quantity is not None:
            raise ValueError('Entrada/saída exige quantidade positiva, sem saldo contado')
        return self


def balance(product):
    return {'id': product.id, 'sku': product.sku, 'name': product.name,
            'unit': product.unit, 'active': product.active, 'version': product.version,
            'stock': format(product.stock, '.3f'), 'stock_min': format(product.stock_min, '.3f'),
            'stock_max': format(product.stock_max, '.3f') if product.stock_max is not None else None,
            'stock_low': product.stock <= product.stock_min}


def movement(row):
    return {'id': row.id, 'product_id': row.product_id, 'sale_id': row.sale_id,
            'operator_id': row.user_id, 'kind': row.kind, 'reason': row.reason,
            'quantity': format(row.quantity, '.3f'), 'before': format(row.before, '.3f'),
            'after': format(row.after, '.3f'), 'created_at': row.created_at.isoformat() + 'Z'}


def fingerprint(body):
    data = body.model_dump(mode='json', exclude={'idempotency_key'})
    for key in ('quantity', 'target_quantity'):
        if data[key] is not None:
            data[key] = str(Decimal(data[key]).normalize())
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


@router.get('')
def balances(user: Read, db: Db, q: str = Query('', max_length=120),
             low_only: bool = False, include_inactive: bool = False,
             after_id: int = Query(0, ge=0), limit: int = Query(8, ge=1, le=25),
             revision: int | None = Query(None, ge=1)):
    state = lock_catalog(db)
    if revision is not None and state.revision != revision:
        raise HTTPException(409, 'Estoque alterado. Reinicie a consulta.')
    query = select(Product).where(Product.id > after_id)
    if not include_inactive:
        query = query.where(Product.active.is_(True))
    if low_only:
        query = query.where(Product.stock <= Product.stock_min)
    if q.strip():
        term = q.strip().replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        query = query.where(or_(Product.name.ilike('%' + term + '%', escape='\\'),
                                Product.sku.ilike('%' + term + '%', escape='\\')))
    rows = db.scalars(query.order_by(Product.id).limit(limit + 1)).all()
    return {'items': [balance(row) for row in rows[:limit]], 'revision': state.revision,
            'next_id': rows[limit - 1].id if len(rows) > limit else None}


@router.post('/adjustments', status_code=201)
def adjust(body: Adjustment, user: Adjust, current: Current, db: Db, request: Request):
    state = lock_catalog(db)
    device = current[0].device_id
    hashed = fingerprint(body)
    previous = db.scalar(select(InventoryRequest).where(
        InventoryRequest.user_id == user.id, InventoryRequest.device_id == device,
        InventoryRequest.idempotency_key == body.idempotency_key).with_for_update())
    if previous:
        if previous.state == 'abandoned':
            raise HTTPException(409, 'Tentativa encerrada. Consulte o saldo e gere nova tentativa.')
        if previous.request_hash != hashed:
            raise HTTPException(409, 'Chave já usada com outro movimento.')
        return {**movement(db.get(StockMovement, previous.movement_id)), 'replayed': True}
    product = db.scalar(select(Product).where(Product.id == body.product_id).with_for_update())
    if not product or not product.active:
        raise HTTPException(409, 'Produto inexistente ou inativo.')
    if product.version != body.product_version:
        raise HTTPException(409, 'Saldo/cadastro alterado. Consulte novamente antes de movimentar.')
    before = product.stock
    after = body.target_quantity if body.kind == 'adjustment' else before + (
        body.quantity if body.kind == 'entry' else -body.quantity)
    if after < 0:
        raise HTTPException(409, 'Saldo insuficiente. Estoque negativo não é permitido.')
    if after > Decimal('999999999999.999'):
        raise HTTPException(409, 'Saldo excede o limite do produto.')
    if after == before:
        raise HTTPException(422, 'Saldo contado igual ao atual: nenhum movimento necessário.')
    row = StockMovement(product_id=product.id, user_id=user.id, kind='inventory_' + body.kind,
                        quantity=after - before, before=before, after=after, reason=body.reason)
    db.add(row)
    db.flush()
    db.add(InventoryRequest(user_id=user.id, device_id=device, idempotency_key=body.idempotency_key,
                            request_hash=hashed, movement_id=row.id))
    product.stock = after
    product.sync_revision = state.revision + 1
    product.version += 1
    product.updated_at = utcnow()
    state.revision += 1
    record(db, request, user, 'inventory.' + body.kind, 'stock_movements', row.id)
    db.commit()
    return {**movement(row), 'replayed': False}


@router.post('/requests/{key}/resolve')
def resolve(key: str, user: Adjust, current: Current, db: Db, request: Request):
    import re
    if not re.fullmatch(r'[A-Za-z0-9_-]{16,64}', key):
        raise HTTPException(422, 'Identificador inválido.')
    lock_catalog(db)
    device = current[0].device_id
    previous = db.scalar(select(InventoryRequest).where(
        InventoryRequest.user_id == user.id, InventoryRequest.device_id == device,
        InventoryRequest.idempotency_key == key).with_for_update())
    if previous and previous.state == 'completed':
        return {'state': 'completed', 'movement': movement(db.get(StockMovement, previous.movement_id))}
    if not previous:
        previous = InventoryRequest(user_id=user.id, device_id=device, idempotency_key=key,
                                    request_hash='', state='abandoned', movement_id=None)
        db.add(previous)
        db.flush()
        record(db, request, user, 'inventory.resolve', 'inventory_requests', previous.id)
        db.commit()
    return {'state': 'abandoned'}


@router.get('/{identity}')
def detail(identity: int, user: Read, db: Db):
    row = db.get(Product, identity)
    if not row:
        raise HTTPException(404, 'Produto não encontrado.')
    return balance(row)


@router.get('/{identity}/movements')
def history(identity: int, user: Read, db: Db, after_id: int = Query(0, ge=0),
            limit: int = Query(8, ge=1, le=25)):
    if not db.get(Product, identity):
        raise HTTPException(404, 'Produto não encontrado.')
    rows = db.scalars(select(StockMovement).where(StockMovement.product_id == identity,
        StockMovement.id > after_id).order_by(StockMovement.id).limit(limit + 1)).all()
    return {'items': [movement(row) for row in rows[:limit]],
            'next_id': rows[limit - 1].id if len(rows) > limit else None}


@router.get('/movements/{identity}')
def movement_detail(identity: int, user: Read, db: Db):
    row = db.get(StockMovement, identity)
    if not row:
        raise HTTPException(404, 'Movimentação não encontrada.')
    return movement(row)
