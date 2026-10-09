"""Security boundaries and failed transactions, exercised through the real API."""
from datetime import timedelta
import uuid
import pytest
from sqlalchemy import event, select, func
from sqlalchemy.exc import OperationalError
from app import main
from app.models import AuditLog, AuthAudit, Product, Sale, Session, User, CatalogState, utcnow
from test_auth import login, headers
from test_products import credentials, product
from test_finance import setup
import re


def test_every_commercial_route_requires_authentication(environment):
    client, _ = environment
    public = {'/api/v1/auth/login','/api/v1/auth/refresh','/api/v1/system/status'}
    checked = 0
    for template, operations in main.app.openapi()['paths'].items():
        if not template.startswith('/api/v1/') or template in public:
            continue
        path = re.sub(r'\{[^}]+\}', '1', template)
        for method in operations:
            if method not in {'get','post','put','delete','patch'}:
                continue
            result = client.request(method,path,json={})
            assert result.status_code == 401, (method, template, result.status_code)
            checked += 1
    assert checked >= 40


def test_login_failure_audit_and_safe_headers(environment):
    client, factory = environment
    secret = 'never-log-this-password'
    for _ in range(5):
        result = login(client, password=secret)
        assert result.status_code == 401 and result.headers['www-authenticate'] == 'Bearer'
    result = login(client)
    assert result.status_code == 429 and result.headers['retry-after'] == '900'
    uuid.UUID(result.headers['x-correlation-id'])
    assert result.headers['cache-control'] == 'no-store'
    assert result.headers['x-content-type-options'] == 'nosniff'
    with factory() as db:
        rows = list(db.scalars(select(AuditLog).where(AuditLog.operation == 'auth.login')))
        assert [row.result for row in rows] == ['denied'] * 5 + ['limited']
        assert all(row.user_id is None and len(row.entity_id) == 64 for row in rows)
        assert all(secret not in str(row.__dict__) and 'admin' not in row.entity_id for row in rows)


def test_request_size_declared_and_streamed_before_authentication(environment):
    client, factory = environment
    result = client.post('/api/v1/auth/login', content=b'x' * 65537)
    assert result.status_code == 413
    assert result.json()['error']['correlation_id'] == result.headers['x-correlation-id']
    result = client.post('/api/v1/auth/login', content=(chunk for chunk in [b'x'*32000, b'y'*34000]))
    assert result.status_code == 413
    assert client.post('/api/v1/auth/login', content=b'{}', headers={'Content-Length':'-1'}).status_code == 400
    assert client.post('/api/v1/auth/login', content=b'{}', headers={'Content-Length':'999999'}).status_code == 413
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(AuthAudit)) == 0
    assert client.get('/health/ready').status_code == 200


def test_unexpected_failure_is_correlated_and_logs_no_secrets(environment, monkeypatch, caplog):
    client, _ = environment
    secret = 'SENSITIVE-SQL-PASSWORD-TOKEN'
    def fail(*args):
        raise RuntimeError(secret)
    monkeypatch.setattr(main, 'verify', fail)
    result = login(client)
    assert result.status_code == 500
    assert result.json()['error']['correlation_id'] == result.headers['x-correlation-id']
    assert secret not in result.text and secret not in caplog.text
    assert 'RuntimeError' in caplog.text and result.headers['x-correlation-id'] in caplog.text
    assert client.get('/health/ready').status_code == 200


@pytest.mark.parametrize('route', ['/api/v1/products','/api/v1/customers','/api/v1/suppliers',
    '/api/v1/sales','/api/v1/inventory','/api/v1/finance/cash/current',
    '/api/v1/reports/stock','/api/v1/sync/products','/api/v1/users','/api/v1/roles','/api/v1/permissions'])
def test_permissions_revoked_during_session(environment, route):
    client, factory = environment
    auth = credentials(environment, 'viewer')
    with factory.begin() as db:
        user = db.scalar(select(User).where(User.username == 'viewer'))
        user.roles.clear()
    assert client.get(route, headers=auth).status_code == 403
    assert client.get(route).status_code == 401
    assert client.get('/api/v1/auth/me', headers=auth).json()['permissions'] == []


def test_inactive_user_revokes_existing_access_and_refresh(environment):
    client, factory = environment
    tokens = login(client).json()
    with factory.begin() as db:
        db.scalar(select(User).where(User.username == 'admin')).active = False
    assert client.get('/api/v1/auth/me', headers=headers(tokens['access_token'])).status_code == 401
    assert client.post('/api/v1/auth/refresh', json={'refresh_token':tokens['refresh_token'], 'device_id':'tab5-test'}).status_code == 401


def test_refresh_preserves_absolute_deadline_and_replay_is_audited(environment):
    client, factory = environment
    original = login(client).json()
    with factory() as db:
        deadline = db.scalar(select(Session.refresh_expires))
    body = {'refresh_token':original['refresh_token'], 'device_id':'tab5-test'}
    rotated = client.post('/api/v1/auth/refresh', json=body).json()
    with factory() as db:
        assert {row.refresh_expires for row in db.scalars(select(Session))} == {deadline}
    assert client.post('/api/v1/auth/refresh', json=body).status_code == 401
    assert client.get('/api/v1/auth/me', headers=headers(rotated['access_token'])).status_code == 401
    with factory() as db:
        row = db.scalar(select(AuditLog).where(AuditLog.operation=='auth.refresh_replay'))
        assert row and row.result=='denied' and original['refresh_token'] not in str(row.__dict__)


def test_report_cursor_rejected_after_restore_epoch_changes(environment):
    client, factory = environment
    auth = credentials(environment)
    for i in range(2):
        assert client.post('/api/v1/products',headers=auth,json=product(sku='EPOCH-'+str(i))).status_code == 201
    first = client.get('/api/v1/reports/stock?limit=1',headers=auth).json()
    with factory.begin() as db:
        state = db.get(CatalogState,1)
        state.epoch = str(uuid.uuid4()) # Same business revision/IDs after restored history.
    result = client.get('/api/v1/reports/stock',headers=auth,params={'limit':1,'offset':1,'revision':first['revision']})
    assert result.status_code == 409


def test_failed_sale_rolls_back_stock_journal_and_retry_keeps_same_key(environment, caplog):
    client, factory, auth, _, _ = setup(environment)
    row = client.post('/api/v1/products',headers=auth,json=product(stock='2',sale_price='190')).json()
    body = {'idempotency_key':'security-rollback-sale-key-001','items':[{'product_id':row['id'],
        'product_version':row['version'],'quantity':'1','expected_unit_price':'190'}],
        'payments':[{'method':'cash','amount':'190'}]}
    engine = factory.kw['bind']
    secret = 'SENSITIVE-DB-PARAMETERS'
    def fail(connection,cursor,statement,parameters,context,executemany):
        if statement.startswith('INSERT INTO sale_payments'):
            raise OperationalError(statement, parameters, Exception(secret))
    event.listen(engine,'before_cursor_execute',fail)
    try:
        result = client.post('/api/v1/sales',headers=auth,json=body)
    finally:
        event.remove(engine,'before_cursor_execute',fail)
    assert result.status_code == 503, result.text
    assert secret not in result.text and secret not in caplog.text
    with factory() as db:
        assert str(db.get(Product,row['id']).stock)=='2.000'
        assert db.scalar(select(func.count()).select_from(Sale))==0
    retry = client.post('/api/v1/sales',headers=auth,json=body)
    assert retry.status_code == 201, retry.text
    replay = client.post('/api/v1/sales',headers=auth,json=body)
    assert replay.status_code == 201 and replay.json()['id']==retry.json()['id']
    assert client.get('/api/v1/products/'+str(row['id']),headers=auth).json()['stock']=='1.000'
