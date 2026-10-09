"""Online-only customer/supplier records with explicit document permissions."""
import re
from typing import Annotated, Literal
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import Field, field_validator
from sqlalchemy import select, or_, delete
from sqlalchemy.exc import IntegrityError
from .dependencies import Db, Input, allowed
from .models import Contact, SupplierProduct, Product, Sale, AuditLog, User, utcnow

router = APIRouter(prefix="/api/v1", tags=["contacts"])
UF = set("AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split())


def document(value, person_type):
    if not value:
        return None
    value = re.sub(r"[. /-]", "", value.upper().strip())
    if person_type == "PF":
        if not re.fullmatch(r"[0-9]{11}", value) or len(set(value)) == 1:
            raise ValueError("CPF inválido")
        numbers = list(map(int, value))
        for size in (9, 10):
            digit = (sum(n * w for n, w in zip(numbers[:size], range(size + 1, 1, -1))) * 10) % 11
            if (0 if digit == 10 else digit) != numbers[size]:
                raise ValueError("CPF inválido")
    else:
        if not re.fullmatch(r"[A-Z0-9]{12}[0-9]{2}", value) or len(set(value)) == 1:
            raise ValueError("CNPJ inválido")
        numbers = [ord(c) - 48 for c in value]
        for size, weights in ((12, [5,4,3,2,9,8,7,6,5,4,3,2]), (13, [6,5,4,3,2,9,8,7,6,5,4,3,2])):
            remainder = sum(n * w for n, w in zip(numbers[:size], weights)) % 11
            if (0 if remainder < 2 else 11 - remainder) != numbers[size]:
                raise ValueError("CNPJ inválido")
    return value


class ContactInput(Input):
    name: str = Field(min_length=1, max_length=120)
    person_type: Literal["PF", "PJ"] = "PF"
    document: str | None = Field(default=None, max_length=18)
    trade_name: str = Field(default="", max_length=120)
    phone: str = Field(default="", max_length=32)
    email: str = Field(default="", max_length=160)
    address: str = Field(default="", max_length=200)
    city: str = Field(default="", max_length=80)
    state: str = Field(default="", max_length=2)
    postal_code: str = Field(default="", max_length=9)
    contact_name: str = Field(default="", max_length=120)
    notes: str = Field(default="", max_length=500)
    active: bool = True

    @field_validator("name", "trade_name", "phone", "email", "address", "city", "contact_name", "notes")
    @classmethod
    def text(cls, value, info):
        value = value.strip()
        if (info.field_name == "name" and not value) or any(ord(c) < 32 for c in value):
            raise ValueError("Texto inválido")
        if info.field_name == "email" and value and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("E-mail inválido")
        return value

    @field_validator("state")
    @classmethod
    def state_value(cls, value):
        value = value.strip().upper()
        if value and value not in UF:
            raise ValueError("UF inválida")
        return value

    @field_validator("postal_code")
    @classmethod
    def postal(cls, value):
        value = value.strip().replace("-", "")
        if value and not re.fullmatch(r"[0-9]{8}", value):
            raise ValueError("CEP inválido")
        return value

    @field_validator("document")
    @classmethod
    def check_document(cls, value, info):
        return document(value, info.data.get("person_type", "PF"))


class ContactEdit(ContactInput):
    version: int = Field(ge=1)


class Search(Input):
    q: str = Field(default="", max_length=120)
    document_query: str | None = Field(default=None, max_length=18)
    after_id: int = Field(default=0, ge=0)
    limit: int = Field(default=8, ge=1, le=25)
    include_inactive: bool = False


class Association(Input):
    product_id: int = Field(ge=1)


def codes(user):
    return {p.code for r in user.roles for p in r.permissions}


def ensure_documents(user, module):
    if module + ".documents" not in codes(user):
        raise HTTPException(403, "Seu perfil não permite consultar ou alterar documentos.")


def payload(row, user, module, detail=True):
    out = {key: getattr(row, key) for key in ("id", "name", "person_type", "trade_name", "active", "version")}
    out["has_document"] = bool(row.document)
    if detail:
        out.update({key: getattr(row, key) for key in ("phone", "email", "address", "city", "state", "postal_code", "contact_name", "notes")})
        out["document"] = row.document if module + ".documents" in codes(user) else None
        out["document_editable"] = module + ".documents" in codes(user)
        out["created_at"] = row.created_at.isoformat() + "Z"
        out["updated_at"] = row.updated_at.isoformat() + "Z"
    return out


def record(db, request, user, module, action, row):
    db.add(AuditLog(user_id=user.id, operation=module + "." + action, entity=module,
        entity_id=str(row.id), result="success", origin="api", correlation_id=request.state.correlation_id))


def load(db, kind, identity):
    row = db.scalar(select(Contact).where(Contact.id == identity, Contact.kind == kind).with_for_update())
    if not row:
        raise HTTPException(404, "Cadastro não encontrado.")
    return row


def commit(db):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Documento já cadastrado neste módulo.")


def register(module, kind):
    Read = Annotated[User, Depends(allowed(module + ".read"))]
    Create = Annotated[User, Depends(allowed(module + ".create"))]
    Edit = Annotated[User, Depends(allowed(module + ".update"))]
    Disable = Annotated[User, Depends(allowed(module + ".delete"))]

    @router.get("/" + module, name=module + "_list")
    def listing(user: Read, db: Db, q: str = Query("", max_length=120),
                document_query: str | None = Query(None, max_length=18),
                after_id: int = Query(0, ge=0), limit: int = Query(8, ge=1, le=25), include_inactive: bool = False):
        query = select(Contact).where(Contact.kind == kind, Contact.id > after_id)
        if not include_inactive:
            query = query.where(Contact.active.is_(True))
        if q.strip():
            pattern = "%" + q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            query = query.where(or_(Contact.name.ilike(pattern, escape="\\"), Contact.trade_name.ilike(pattern, escape="\\")))
        if document_query is not None:
            ensure_documents(user, module)
            try:
                value = document(document_query, "PF" if len(re.sub(r"[. /-]", "", document_query)) == 11 else "PJ")
            except ValueError:
                raise HTTPException(422, "Documento inválido para pesquisa.")
            if not value:
                raise HTTPException(422, "Informe um documento válido para pesquisa.")
            query = query.where(Contact.document == value)
        rows = db.scalars(query.order_by(Contact.id).limit(limit + 1)).all()
        return {"items": [payload(row, user, module, False) for row in rows[:limit]],
                "next_id": rows[limit - 1].id if len(rows) > limit else None}

    @router.post("/" + module + "/search", name=module + "_search")
    def search(body: Search, user: Read, db: Db):
        return listing(user, db, body.q, body.document_query, body.after_id, body.limit, body.include_inactive)

    @router.post("/" + module, status_code=201, name=module + "_create")
    def create(body: ContactInput, user: Create, db: Db, request: Request):
        if kind == "supplier" and body.person_type != "PJ":
            raise HTTPException(422, "Fornecedor deve usar tipo PJ e CNPJ opcional.")
        if body.document:
            ensure_documents(user, module)
        row = Contact(kind=kind, **body.model_dump())
        db.add(row)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, "Documento já cadastrado neste módulo.")
        record(db, request, user, module, "create", row)
        commit(db)
        return payload(row, user, module)

    @router.get("/" + module + "/{identity}", name=module + "_get")
    def detail(identity: int, user: Read, db: Db, request: Request):
        row = load(db, kind, identity)
        record(db, request, user, module, "read", row)
        db.commit()
        return payload(row, user, module)

    @router.put("/" + module + "/{identity}", name=module + "_edit")
    def edit(identity: int, body: ContactEdit, user: Edit, db: Db, request: Request):
        row = load(db, kind, identity)
        if row.version != body.version:
            raise HTTPException(409, "Cadastro alterado por outro usuário. Consulte novamente antes de editar.")
        if not body.active and row.active and module + ".delete" not in codes(user):
            raise HTTPException(403, "Seu perfil não permite inativar cadastros.")
        if kind == "supplier" and body.person_type != "PJ":
            raise HTTPException(422, "Fornecedor deve usar tipo PJ.")
        values = body.model_dump(exclude={"version"})
        if module + ".documents" not in codes(user):
            if body.document is not None or body.person_type != row.person_type:
                ensure_documents(user, module)
            values.pop("document")  # Hidden document remains untouched on ordinary edits.
        for key, value in values.items():
            setattr(row, key, value)
        row.version += 1
        row.updated_at = utcnow()
        record(db, request, user, module, "update", row)
        commit(db)
        return payload(row, user, module)

    @router.delete("/" + module + "/{identity}", name=module + "_disable")
    def disable(identity: int, version: int, user: Disable, db: Db, request: Request):
        row = load(db, kind, identity)
        if row.version != version:
            raise HTTPException(409, "Cadastro alterado. Consulte novamente.")
        row.active = False
        row.version += 1
        row.updated_at = utcnow()
        record(db, request, user, module, "disable", row)
        commit(db)
        return payload(row, user, module)

    @router.get("/" + module + "/{identity}/history", name=module + "_history")
    def history(identity: int, user: Read, db: Db, after_id: int = Query(0, ge=0), limit: int = Query(8, ge=1, le=25)):
        load(db, kind, identity)
        events = db.scalars(select(AuditLog).where(AuditLog.entity == module,
            AuditLog.entity_id == str(identity), AuditLog.id > after_id, AuditLog.operation != module + ".read")
            .order_by(AuditLog.id).limit(limit + 1)).all()
        return {"items": [{"id": e.id, "operation": e.operation, "created_at": e.created_at.isoformat() + "Z"} for e in events[:limit]],
                "next_id": events[limit-1].id if len(events) > limit else None,
                "purchases_available": kind == "customer" and "sales.read" in codes(user), "message": "Alterações cadastrais abaixo; compras disponíveis na consulta do cliente."}

    if kind == "customer":
        @router.get("/customers/{identity}/purchases", name="customer_purchases")
        def purchases(identity: int, user: Read, db: Db, after_id: int = Query(0, ge=0), limit: int = Query(8, ge=1, le=25)):
            load(db, kind, identity)
            if "sales.read" not in codes(user):
                raise HTTPException(403, "Sem permissão para consultar vendas.")
            from .sales import serialize
            rows = db.scalars(select(Sale).where(Sale.customer_id == identity, Sale.id > after_id).order_by(Sale.id).limit(limit+1)).all()
            return {"items": [serialize(row, False) for row in rows[:limit]], "next_id": rows[limit-1].id if len(rows)>limit else None}

register("customers", "customer")
register("suppliers", "supplier")
SupplierRead = Annotated[User, Depends(allowed("suppliers.read"))]
SupplierEdit = Annotated[User, Depends(allowed("suppliers.update"))]

@router.get("/suppliers/{identity}/products")
def supplier_products(identity: int, user: SupplierRead, db: Db, after_id: int = Query(0, ge=0), limit: int = Query(8, ge=1, le=25)):
    load(db, "supplier", identity)
    if "products.read" not in codes(user):
        raise HTTPException(403, "Sem permissão para consultar produtos.")
    rows = db.execute(select(Product.id, Product.sku, Product.name).join(SupplierProduct, SupplierProduct.product_id == Product.id)
        .where(SupplierProduct.supplier_id == identity, Product.id > after_id).order_by(Product.id).limit(limit+1)).all()
    return {"items": [{"id": r.id, "sku": r.sku, "name": r.name} for r in rows[:limit]], "next_id": rows[limit-1].id if len(rows)>limit else None}

@router.post("/suppliers/{identity}/products", status_code=201)
def associate(identity: int, body: Association, user: SupplierEdit, db: Db, request: Request):
    row = load(db, "supplier", identity)
    if "products.read" not in codes(user):
        raise HTTPException(403, "Sem permissão para consultar produtos.")
    product = db.get(Product, body.product_id)
    if not product:
        raise HTTPException(404, "Produto não encontrado.")
    if not row.active or not product.active:
        raise HTTPException(409, "Fornecedor e produto precisam estar ativos para criar vínculo.")
    if not db.get(SupplierProduct, (identity, body.product_id)):
        db.add(SupplierProduct(supplier_id=identity, product_id=body.product_id))
    record(db, request, user, "suppliers", "associate_product", row)
    db.commit()
    return {"product_id": body.product_id}

@router.delete("/suppliers/{identity}/products/{product_id}", status_code=204)
def disassociate(identity: int, product_id: int, user: SupplierEdit, db: Db, request: Request):
    row = load(db, "supplier", identity)
    db.execute(delete(SupplierProduct).where(SupplierProduct.supplier_id == identity, SupplierProduct.product_id == product_id))
    record(db, request, user, "suppliers", "disassociate_product", row)
    db.commit()
