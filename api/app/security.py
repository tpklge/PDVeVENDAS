import hashlib
import secrets
from datetime import timedelta
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from sqlalchemy import select
from .models import Session, User, utcnow

# Argon2id: 64 MiB, 3 iterations, 2 lanes. Measure on the target server.
hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)
DUMMY_HASH = hasher.hash(secrets.token_urlsafe(32))

def digest(value: str):
    return hashlib.sha256(value.encode()).hexdigest()

def verify(encoded: str, password: str):
    try:
        return hasher.verify(encoded, password)
    except (VerificationError, InvalidHashError):
        return False

def lock_user(db, user_id):
    # Authentication mutations all take the user lock before session locks.
    # Refresh must not create a session after password reset/logout has revoked it.
    return db.scalar(select(User).where(User.id == user_id).with_for_update()
                     .execution_options(populate_existing=True))

def lock_session(db, session_id):
    return db.scalar(select(Session).where(Session.id == session_id).with_for_update()
                     .execution_options(populate_existing=True))

def issue_session(db, user, device_id, family=None, refresh_expires=None):
    access = secrets.token_urlsafe(32)
    refresh = secrets.token_urlsafe(48)
    now = utcnow()
    db.add(Session(user_id=user.id, device_id=device_id,
        family=family or secrets.token_hex(24), access_hash=digest(access),
        refresh_hash=digest(refresh), access_expires=now + timedelta(minutes=15),
        refresh_expires=refresh_expires or now + timedelta(hours=8)))
    return {"access_token": access, "refresh_token": refresh, "token_type": "bearer", "expires_in": 900}
