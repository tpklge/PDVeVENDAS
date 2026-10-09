"""Authentication races on disposable MariaDB, including controlled password reset."""
import os
if os.environ.get('CI') != 'true':
    raise SystemExit('Teste permitido apenas em CI isolado.')
import json
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from types import SimpleNamespace
from sqlalchemy import select, update, event
from fastapi import HTTPException
from app.db import SessionFactory, engine
from app.models import User, Session, AuditLog
from app.security import hasher
from app.main import refresh, Refresh

PASSWORD='ci-security-isolated-password'
with SessionFactory.begin() as db:
    user=User(username='ci-security',password_hash=hasher.hash(PASSWORD),must_change_password=False)
    db.add(user);db.flush();user_id=user.id

def call(method,path,body=None,token=None):
    headers={'Content-Type':'application/json'}
    if token:headers['Authorization']='Bearer '+token
    req=urllib.request.Request('http://api:8000'+path,headers=headers,method=method,
        data=json.dumps(body).encode() if body is not None else None)
    try:response=urllib.request.urlopen(req,timeout=30)
    except urllib.error.HTTPError as error:response=error
    with response:
        raw=response.read();return response.status,json.loads(raw) if raw else None

def login():
    code,tokens=call('POST','/api/v1/auth/login',{'username':'ci-security','password':PASSWORD,'device_id':'ci-security'})
    assert code==200,(code,tokens)
    return tokens

def race(tokens):
    barrier=Barrier(2)
    def submit(_):
        barrier.wait(timeout=10)
        return call('POST','/api/v1/auth/refresh',{'refresh_token':tokens['refresh_token'],'device_id':'ci-security'})
    with ThreadPoolExecutor(max_workers=2) as pool:return list(pool.map(submit,range(2)))

original=login();results=race(original)
assert sorted(code for code,_ in results)==[200,401],results
rotated=next(body for code,body in results if code==200)
assert call('GET','/api/v1/auth/me',token=rotated['access_token'])[0]==401
with SessionFactory() as db:
    assert db.scalar(select(AuditLog).where(AuditLog.operation=='auth.refresh_replay',AuditLog.user_id==user_id))

# Hold the user row while reset revokes all sessions. A renewal already reading
# the old token must wait and observe revocation after the reset commits.
original=login();waiting=Event()
def before_lock(connection,cursor,statement,parameters,context,executemany):
    if 'FROM users' in statement and 'FOR UPDATE' in statement:
        waiting.set()
event.listen(engine,'before_cursor_execute',before_lock)
def blocked_refresh():
    with SessionFactory() as db:
        try:
            refresh(Refresh(refresh_token=original['refresh_token'],device_id='ci-security'),
                SimpleNamespace(state=SimpleNamespace(correlation_id='ci-controlled-race')),db)
        except HTTPException as exc:
            return exc.status_code
        return 200
try:
    with ThreadPoolExecutor(max_workers=1) as pool:
        with SessionFactory.begin() as db:
            user=db.scalar(select(User).where(User.id==user_id).with_for_update())
            waiting.clear()
            user.password_hash=hasher.hash('ci-security-reset-password')
            db.execute(update(Session).where(Session.user_id==user_id).values(revoked=True))
            future=pool.submit(blocked_refresh)
            assert waiting.wait(timeout=10),'Refresh did not reach the user lock'
        assert future.result(timeout=20)==401
finally:
    event.remove(engine,'before_cursor_execute',before_lock)
assert call('GET','/api/v1/auth/me',token=original['access_token'])[0]==401
with SessionFactory() as db:
    assert not list(db.scalars(select(Session).where(Session.user_id==user_id,Session.revoked.is_(False))))
print('PASS: MariaDB real — refresh simultâneo, replay revoga família, reset concorrente bloqueia nova sessão e auditoria sem credenciais.')
