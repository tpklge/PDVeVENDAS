"""Validated catalog, exact decimal values and revisioned pagination."""
from decimal import Decimal
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import Field, field_validator, model_validator
from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from .dependencies import Db, Input, allowed
from .models import AuditLog, CatalogState, Category, Product, User, utcnow

router = APIRouter(prefix="/api/v1", tags=["products"])
Read = Annotated[User, Depends(allowed("products.read"))]
Create = Annotated[User, Depends(allowed("products.create"))]
Edit = Annotated[User, Depends(allowed("products.update"))]
Delete = Annotated[User, Depends(allowed("products.delete"))]


class CategoryInput(Input):
    name: str = Field(min_length=1, max_length=80)

    @field_validator("name")
    @classmethod
    def clean(cls, value):
        value = value.strip()
        if not value or any(ord(c) < 32 for c in value):
            raise ValueError("Nome inválido")
        return value


class ProductInput(Input):
    sku: str = Field(min_length=1, max_length=32, pattern=r"^[A-Za-z0-9._-]+$")
    barcode: str | None = Field(default=None, pattern=r"^([0-9]{8}|[0-9]{12}|[0-9]{13}|[0-9]{14})$")
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)
    category: str = Field(default="", max_length=80)
    unit: str = Field(default="UN", min_length=1, max_length=8, pattern=r"^[A-Za-z0-9]+$")
    cost_price: Decimal = Field(default=Decimal("0"), ge=0, max_digits=12, decimal_places=2)
    sale_price: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    stock: Decimal = Field(default=Decimal("0"), ge=0, max_digits=15, decimal_places=3)
    stock_min: Decimal = Field(default=Decimal("0"), ge=0, max_digits=15, decimal_places=3)
    stock_max: Decimal | None = Field(default=None, ge=0, max_digits=15, decimal_places=3)
    active: bool = True
    ncm: str | None = Field(default=None, pattern=r"^[0-9]{8}$")
    cest: str | None = Field(default=None, pattern=r"^[0-9]{7}$")
    origin: int | None = Field(default=None, ge=0, le=8)

    @field_validator("name", "description", "category")
    @classmethod
    def clean_text(cls, value, info):
        value = value.strip()
        if (info.field_name == "name" and not value) or any(ord(c) < 32 for c in value):
            raise ValueError("Texto inválido")
        return value

    @field_validator("sku", "unit")
    @classmethod
    def upper(cls, value):
        return value.upper()

    @field_validator("barcode")
    @classmethod
    def check_gtin(cls, value):
        if value:
            digits = list(map(int, value))
            total = sum(d * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(digits[:-1])))
            if (10 - total % 10) % 10 != digits[-1]:
                raise ValueError("Dígito verificador GTIN inválido")
        return value

    @model_validator(mode="after")
    def stock_limits(self):
        if self.stock_max is not None and self.stock_max < self.stock_min:
            raise ValueError("Estoque máximo menor que mínimo")
        return self


class ProductEdit(ProductInput):
    version: int = Field(ge=1)


def lock_catalog(db):
    return db.scalar(select(CatalogState).where(CatalogState.id == 1).with_for_update())


def serialize(product):
    result = {key: getattr(product, key) for key in (
        "id", "sku", "barcode", "name", "description", "unit", "active", "ncm", "cest", "origin", "version")}
    result["category"] = product.category.name if product.category else ""
    for key in ("cost_price", "sale_price", "stock", "stock_min", "stock_max"):
        value = getattr(product, key)
        result[key] = format(value, ".2f" if key in {"cost_price", "sale_price"} else ".3f") if value is not None else None
    result["stock_low"] = product.stock <= product.stock_min
    result["created_at"] = product.created_at.isoformat() + "Z"
    result["updated_at"] = product.updated_at.isoformat() + "Z"
    return result


def record(db, request, user, operation, entity, entity_id):
    db.add(AuditLog(user_id=user.id, operation=operation, entity=entity, entity_id=str(entity_id),
        result="success", origin="api", correlation_id=request.state.correlation_id))


def commit(db):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "SKU, código de barras ou categoria já cadastrado.")


def assign(db, product, body):
    fields = body.model_dump(exclude={"category", "version"})
    for key, value in fields.items():
        setattr(product, key, value)
    category = db.scalar(select(Category).where(Category.name == body.category).with_for_update()) if body.category else None
    if body.category and not category:
        category = Category(name=body.category)
        db.add(category)
        db.flush()
    product.category = category


@router.get("/categories")
def categories(user: Read, db: Db, after_id: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
    rows = db.scalars(select(Category).where(Category.id > after_id).order_by(Category.id).limit(limit + 1)).all()
    return {"items": [{"id": c.id, "name": c.name} for c in rows[:limit]],
            "next_id": rows[limit - 1].id if len(rows) > limit else None}


@router.post("/categories", status_code=201)
def create_category(body: CategoryInput, user: Create, db: Db, request: Request):
    state = lock_catalog(db)
    row = Category(name=body.name)
    db.add(row)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Categoria já cadastrada.")
    state.revision += 1
    record(db, request, user, "categories.create", "categories", row.id)
    commit(db)
    return {"id": row.id, "name": row.name}


@router.put("/categories/{category_id}")
def rename_category(category_id: int, body: CategoryInput, user: Edit, db: Db, request: Request):
    state = lock_catalog(db)
    category = db.get(Category, category_id)
    if not category:
        raise HTTPException(404, "Categoria não encontrada.")
    category.name = body.name
    db.execute(update(Product).where(Product.category_id == category.id).values(version=Product.version + 1, updated_at=utcnow()))
    state.revision += 1
    record(db, request, user, "categories.update", "categories", category.id)
    commit(db)
    return {"id": category.id, "name": category.name}


@router.get("/products")
def list_products(user: Read, db: Db, after_id: int = Query(0, ge=0), limit: int = Query(10, ge=1, le=50),
                  q: str = Query("", max_length=120), category: str = Query("", max_length=80),
                  include_inactive: bool = False, revision: int | None = Query(None, ge=1)):
    state = lock_catalog(db)
    if revision is not None and revision != state.revision:
        raise HTTPException(409, "Catálogo mudou durante a leitura. Atualize novamente.")
    query = select(Product).where(Product.id > after_id)
    if not include_inactive:
        query = query.where(Product.active.is_(True))
    if q:
        query = query.where(or_(func.lower(Product.name).contains(q.lower(), autoescape=True),
            func.lower(Product.sku).contains(q.lower(), autoescape=True), Product.barcode == q))
    if category:
        query = query.join(Category).where(Category.name == category)
    rows = db.scalars(query.order_by(Product.id).limit(limit + 1).with_for_update()).unique().all()
    return {"revision": state.revision, "items": [serialize(p) for p in rows[:limit]],
            "next_id": rows[limit - 1].id if len(rows) > limit else None}


@router.get("/products/{product_id}")
def get_product(product_id: int, user: Read, db: Db):
    row = db.get(Product, product_id, with_for_update=True)
    if not row:
        raise HTTPException(404, "Produto não encontrado.")
    return serialize(row)


@router.post("/products", status_code=201)
def create_product(body: ProductInput, user: Create, db: Db, request: Request):
    state = lock_catalog(db)
    product = Product()
    try:
        assign(db, product, body)
        db.add(product)
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "SKU ou código de barras já cadastrado.")
    state.revision += 1
    record(db, request, user, "products.create", "products", product.id)
    commit(db)
    return serialize(product)


@router.put("/products/{product_id}")
def edit_product(product_id: int, body: ProductEdit, user: Edit, db: Db, request: Request):
    state = lock_catalog(db)
    product = db.get(Product, product_id, with_for_update=True)
    if not product:
        raise HTTPException(404, "Produto não encontrado.")
    if product.version != body.version:
        raise HTTPException(409, "Produto alterado por outro usuário. Atualize antes de editar.")
    codes = {p.code for r in user.roles for p in r.permissions}
    if product.stock != body.stock and "inventory.adjust" not in codes:
        raise HTTPException(403, "Sem permissão para ajustar estoque.")
    if product.active and not body.active and "products.delete" not in codes:
        raise HTTPException(403, "Sem permissão para inativar produto.")
    try:
        assign(db, product, body)
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "SKU ou código de barras já cadastrado.")
    product.version += 1
    product.updated_at = utcnow()
    state.revision += 1
    record(db, request, user, "products.update", "products", product.id)
    commit(db)
    return serialize(product)


@router.delete("/products/{product_id}", status_code=204)
def deactivate_product(product_id: int, user: Delete, db: Db, request: Request, version: int = Query(..., ge=1)):
    state = lock_catalog(db)
    product = db.get(Product, product_id, with_for_update=True)
    if not product:
        raise HTTPException(404, "Produto não encontrado.")
    if product.version != version:
        raise HTTPException(409, "Produto alterado. Atualize antes de inativar.")
    product.active = False
    product.version += 1
    product.updated_at = utcnow()
    state.revision += 1
    record(db, request, user, "products.deactivate", "products", product.id)
    commit(db)
