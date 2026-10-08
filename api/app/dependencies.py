from typing import Annotated
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession
from .db import get_db
from .models import Session, User, utcnow
from .security import digest

bearer = HTTPBearer(auto_error=False)
Db = Annotated[DbSession, Depends(get_db)]

class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


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


