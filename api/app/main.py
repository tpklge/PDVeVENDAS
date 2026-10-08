import uuid
from datetime import timedelta
from typing import Annotated
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select, text, update
from sqlalchemy.orm import Session as DbSession
from .config import VERSION, SCHEMA_REVISION
from .db import get_db
from .models import AuditLog, AuthAudit, Permission, Role, Session, User, utcnow
from .security import DUMMY_HASH, digest, hasher, issue_session, verify

app = FastAPI(title="TAB5 ERP", version=VERSION, description="Fundação de autenticação e infraestrutura. Não contém PDV nesta versão.")
bearer = HTTPBearer(auto_error=False)
Db = Annotated[DbSession, Depends(get_db)]


@app.middleware("http")
async def correlation(request: Request, call_next):
    request.state.correlation_id = str(uuid.uuid4())
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = request.state.correlation_id
    response.headers["Cache-Control"] = "no-store"
    return response


def error_response(request, status, code, message):
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message,
        "correlation_id": getattr(request.state, "correlation_id", str(uuid.uuid4()))}})


@app.exception_handler(HTTPException)
async def http_error(request, exc):
    return error_response(request, exc.status_code, f"HTTP_{exc.status_code}", str(exc.detail))


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    return error_response(request, 422, "VALIDATION_ERROR", "Verifique os campos informados.")


@app.exception_handler(Exception)
async def unexpected_error(request, exc):
    return error_response(request, 500, "INTERNAL_ERROR", "Não foi possível concluir a operação.")


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


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


def current_session(db: Db, token: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]):
    session = db.scalar(select(Session).where(Session.access_hash == digest(token.credentials))) if token else None
    if not session or session.revoked or session.access_expires <= utcnow():
        raise HTTPException(401, "Sessão inválida ou expirada.")
    user = db.get(User, session.user_id)
    if not user or not user.active:
        raise HTTPException(401, "Sessão inválida ou expirada.")
    return session, user


Current = Annotated[tuple[Session, User], Depends(current_session)]


def allowed(code):
    def dependency(current: Current):
        _, user = current
        if user.must_change_password:
            raise HTTPException(403, "Altere a senha inicial antes de continuar.")
        codes = {p.code for r in user.roles for p in r.permissions}
        if code not in codes:
            raise HTTPException(403, "Você não tem permissão para esta operação.")
        return user
    return dependency


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
    return {"version": VERSION, "api_version": "v1", "capabilities": ["auth", "rbac"], "commercial_operations": False}


@app.post("/api/v1/auth/login")
def login(body: Login, request: Request, db: Db):
    user = db.scalar(select(User).where(User.username == body.username).with_for_update())
    subject = digest(body.username)
    recent = utcnow() - timedelta(minutes=15)
    failures = db.scalar(select(func.count()).select_from(AuthAudit).where(
        AuthAudit.subject_hash == subject, AuthAudit.success.is_(False), AuthAudit.created_at >= recent))
    if failures >= 5:
        raise HTTPException(429, "Muitas tentativas. Aguarde 15 minutos.")
    valid = verify(user.password_hash if user else DUMMY_HASH, body.password)
    success = bool(user and valid and user.active)
    db.add(AuthAudit(subject_hash=subject, success=success))
    if not success:
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
    session = db.scalar(select(Session).where(Session.refresh_hash == digest(body.refresh_token)).with_for_update())
    if not session or session.device_id != body.device_id:
        raise HTTPException(401, "Sessão inválida ou expirada.")
    user = db.get(User, session.user_id)
    if session.revoked:
        db.execute(update(Session).where(Session.family == session.family).values(revoked=True))
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
