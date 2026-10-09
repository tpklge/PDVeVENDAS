import uuid
import logging
from datetime import timedelta
from typing import Annotated
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import Field
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import SQLAlchemyError
from .config import VERSION, SCHEMA_REVISION
from .db import get_db
from .models import AuditLog, AuthAudit, Permission, Role, Session, User, utcnow
from .security import DUMMY_HASH, digest, hasher, issue_session, verify, lock_user, lock_session
from .request_limits import RequestLimit

app = FastAPI(title="TAB5 ERP", version=VERSION, description="Gestão comercial, PDV, estoque, caixa e financeiro.")
app.add_middleware(RequestLimit)
logger = logging.getLogger("tab5.security")
from .dependencies import Db, Input, Current, allowed


@app.middleware("http")
async def correlation(request: Request, call_next):
    request.state.correlation_id = str(uuid.uuid4())
    try:
        response = await call_next(request)
    except Exception as exc:
        # Do not log SQL parameters, bodies, tokens, exception strings or tracebacks.
        logger.error("request_failed correlation_id=%s type=%s", request.state.correlation_id, type(exc).__name__)
        response = error_response(request, 503 if isinstance(exc, SQLAlchemyError) else 500,
                                  "SERVICE_UNAVAILABLE" if isinstance(exc, SQLAlchemyError) else "INTERNAL_ERROR",
                                  "Não foi possível concluir a operação. Verifique antes de reenviar.")
    response.headers["X-Correlation-ID"] = request.state.correlation_id
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


def error_response(request, status, code, message):
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message,
        "correlation_id": getattr(request.state, "correlation_id", str(uuid.uuid4()))}})


@app.exception_handler(HTTPException)
async def http_error(request, exc):
    response = error_response(request, exc.status_code, f"HTTP_{exc.status_code}", str(exc.detail))
    if exc.status_code == 401:
        response.headers["WWW-Authenticate"] = "Bearer"
    if exc.status_code == 429:
        response.headers["Retry-After"] = "900"
    return response


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    labels = {"sku": "SKU", "barcode": "GTIN/EAN e dígito verificador", "name": "Nome", "category": "Categoria",
        "sale_price": "Preço de venda (até 2 casas)", "cost_price": "Preço de custo (até 2 casas)",
        "stock": "Estoque (até 3 casas)", "stock_min": "Estoque mínimo", "stock_max": "Estoque máximo",
        "ncm": "NCM (8 dígitos)", "cest": "CEST (7 dígitos)", "origin": "Origem (0 a 8)", "document": "CPF/CNPJ (tipo e dígitos verificadores)", "person_type": "Tipo PF/PJ", "email": "E-mail", "state": "UF", "postal_code": "CEP (8 dígitos, hífen opcional)", "address": "Endereço", "city": "Cidade", "notes": "Observações", "quantity": "Quantidade (até 3 casas)", "items": "Itens do carrinho", "discount_amount": "Desconto em valor", "discount_percent": "Desconto percentual", "payments": "Pagamentos", "amount": "Valor do pagamento", "method": "Forma de pagamento", "reason": "Justificativa", "idempotency_key": "Identificador da tentativa", "expected_unit_price": "Preço unitário", "product_version": "Versão do produto", "target_quantity": "Saldo contado (até 3 casas)", "kind": "Tipo de movimentação", "due_date": "Vencimento (AAAA-MM-DD)", "category_id": "Categoria financeira", "contact_id": "Cliente/fornecedor", "description": "Descrição", "session_id": "Caixa", "last_movement_id": "Revisão do caixa", "version": "Versão da conta", "from_date": "Data inicial", "to_date": "Data final"}
    names = sorted({labels.get(str(error["loc"][-1]), "campos informados") for error in exc.errors()})
    return error_response(request, 422, "VALIDATION_ERROR", "Verifique: " + ", ".join(names) + ".")


class Login(Input):
    username: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9_.@+-]+$")
    password: str = Field(min_length=1, max_length=128)
    device_id: str = Field(min_length=1, max_length=80)


class Refresh(Input):
    refresh_token: str = Field(min_length=40, max_length=128)
    device_id: str = Field(min_length=1, max_length=80)


class PasswordChange(Input):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


def audit(db, request, user, operation, origin):
    db.add(AuditLog(user_id=user.id, operation=operation, entity="users", entity_id=str(user.id),
        result="success", origin=origin, correlation_id=request.state.correlation_id))


@app.get("/health/live")
def live():
    return {"status": "ok"}


@app.get("/health/ready")
def ready(db: Db):
    try:
        revision = db.scalar(text("SELECT version_num FROM alembic_version"))
        if revision != SCHEMA_REVISION:
            raise ValueError("schema")
    except Exception:
        raise HTTPException(503, "Serviço temporariamente indisponível.")
    return {"status": "ready"}


@app.get("/api/v1/system/status")
def status():
    return {"version": VERSION, "api_version": "v1", "capabilities": ["auth", "rbac", "products", "catalog_snapshot", "customers", "suppliers", "sales", "declared_payments", "inventory", "cash", "finance", "reports", "incremental_sync", "offline_drafts"], "commercial_operations": True}


@app.post("/api/v1/auth/login")
def login(body: Login, request: Request, db: Db):
    user = db.scalar(select(User).where(User.username == body.username).with_for_update())
    subject = digest(body.username)
    recent = utcnow() - timedelta(minutes=15)
    failures = db.scalar(select(func.count()).select_from(AuthAudit).where(
        AuthAudit.subject_hash == subject, AuthAudit.success.is_(False), AuthAudit.created_at >= recent))
    if failures >= 5:
        db.add(AuditLog(user_id=None, operation="auth.login", entity="auth_subject", entity_id=subject,
                       result="limited", origin="api", correlation_id=request.state.correlation_id))
        db.commit()
        raise HTTPException(429, "Muitas tentativas. Aguarde 15 minutos.")
    valid = verify(user.password_hash if user else DUMMY_HASH, body.password)
    success = bool(user and valid and user.active)
    db.add(AuthAudit(subject_hash=subject, success=success))
    if not success:
        db.add(AuditLog(user_id=None, operation="auth.login", entity="auth_subject", entity_id=subject,
                       result="denied", origin="api", correlation_id=request.state.correlation_id))
        db.commit()
        raise HTTPException(401, "Usuário ou senha inválidos.")
    if hasher.check_needs_rehash(user.password_hash):
        user.password_hash = hasher.hash(body.password)
    tokens = issue_session(db, user, body.device_id)
    audit(db, request, user, "auth.login", body.device_id)
    db.commit()
    return {**tokens, "must_change_password": user.must_change_password}


@app.post("/api/v1/auth/refresh")
def refresh(body: Refresh, request: Request, db: Db):
    session = db.scalar(select(Session).where(Session.refresh_hash == digest(body.refresh_token)))
    if not session or session.device_id != body.device_id:
        raise HTTPException(401, "Sessão inválida ou expirada.")
    user = lock_user(db, session.user_id)
    session = lock_session(db, session.id)
    if not session:
        raise HTTPException(401, "Sessão inválida ou expirada.")
    if session.revoked:
        db.execute(update(Session).where(Session.family == session.family).values(revoked=True))
        if user:
            db.add(AuditLog(user_id=user.id, operation="auth.refresh_replay", entity="users", entity_id=str(user.id),
                           result="denied", origin=session.device_id, correlation_id=request.state.correlation_id))
        db.commit()
        raise HTTPException(401, "Sessão revogada. Entre novamente.")
    if session.refresh_expires <= utcnow() or not user or not user.active:
        raise HTTPException(401, "Sessão inválida ou expirada.")
    session.revoked = True
    tokens = issue_session(db, user, body.device_id, session.family, session.refresh_expires)
    audit(db, request, user, "auth.refresh", body.device_id)
    db.commit()
    return tokens


@app.post("/api/v1/auth/logout", status_code=204)
def logout(current: Current, db: Db, request: Request):
    session, user = current
    lock_user(db, user.id)
    db.execute(update(Session).where(Session.family == session.family).values(revoked=True))
    audit(db, request, user, "auth.logout", session.device_id)
    db.commit()


@app.get("/api/v1/auth/me")
def me(current: Current):
    session, user = current
    return {"id": user.id, "username": user.username, "device_id": session.device_id,
        "must_change_password": user.must_change_password, "roles": [r.name for r in user.roles],
        "permissions": sorted({p.code for r in user.roles for p in r.permissions})}


@app.post("/api/v1/auth/change-password", status_code=204)
def change_password(body: PasswordChange, current: Current, request: Request, db: Db):
    session, user = current
    user = lock_user(db, user.id)
    session = lock_session(db, session.id)
    if not user or not user.active or not session or session.revoked or session.access_expires <= utcnow():
        raise HTTPException(401, "Sessão inválida ou expirada.")
    if not verify(user.password_hash, body.current_password):
        raise HTTPException(401, "Senha atual inválida.")
    if body.current_password == body.new_password:
        raise HTTPException(422, "Escolha uma senha diferente da atual.")
    user.password_hash = hasher.hash(body.new_password)
    user.must_change_password = False
    db.execute(update(Session).where(Session.user_id == user.id).values(revoked=True))
    audit(db, request, user, "auth.change_password", session.device_id)
    db.commit()


@app.get("/api/v1/roles")
def roles(db: Db, user: Annotated[User, Depends(allowed("users.read"))]):
    return [{"id": r.id, "name": r.name, "permissions": sorted(p.code for p in r.permissions)} for r in db.scalars(select(Role))]


@app.get("/api/v1/permissions")
def permissions(db: Db, user: Annotated[User, Depends(allowed("users.read"))]):
    return {"items": list(db.scalars(select(Permission.code).order_by(Permission.code)))}


@app.get("/api/v1/users")
def users(db: Db, user: Annotated[User, Depends(allowed("users.read"))],
          offset: int = Query(0, ge=0), limit: int = Query(25, ge=1, le=100)):
    rows = db.scalars(select(User).order_by(User.id).offset(offset).limit(limit))
    return {"items": [{"id": u.id, "username": u.username, "active": u.active} for u in rows], "offset": offset, "limit": limit}


from .products import router as products_router
app.include_router(products_router)

from .contacts import router as contacts_router
app.include_router(contacts_router)

from .inventory import router as inventory_router
from .sales import router as sales_router
app.include_router(sales_router)
app.include_router(inventory_router)

from .finance import router as finance_router
app.include_router(finance_router)

from .reports import router as reports_router
app.include_router(reports_router)

from .sync import router as sync_router
app.include_router(sync_router)
