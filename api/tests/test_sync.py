from uuid import uuid4
from test_products import credentials, product
from test_finance import setup
from test_reports import sell

URL = '/api/v1/sync/products'


def sync(client, auth, **params):
    response = client.get(URL, headers=auth, params=params)
    assert response.status_code == 200, response.text
    return response.json()


def test_snapshot_incremental_edit_deactivate_and_category(environment):
    client, _ = environment
    auth = credentials(environment)
    one = client.post('/api/v1/products', headers=auth, json=product(sku='SYNC-A', category='Inicial')).json()
    two = client.post('/api/v1/products', headers=auth, json=product(sku='SYNC-B')).json()
    initial = sync(client, auth)
    assert len(initial['epoch']) == 36 and {p['id'] for p in initial['items']} == {one['id'], two['id']}
    params = {'since': initial['revision'], 'epoch': initial['epoch']}
    assert sync(client, auth, **params)['items'] == []
    assert client.put('/api/v1/products/'+str(one['id']), headers=auth,
        json={**product(sku='SYNC-A', category='Inicial', sale_price='190'), 'version':one['version']}).status_code == 200
    delta = sync(client, auth, **params)
    assert [p['id'] for p in delta['items']] == [one['id']]
    assert delta['items'][0]['sale_price'] == '190.00'
    assert client.delete('/api/v1/products/'+str(two['id']), headers=auth, params={'version':two['version']}).status_code == 204
    assert next(p for p in sync(client, auth, **params)['items'] if p['id']==two['id'])['active'] is False
    before = sync(client, auth)
    category = client.get('/api/v1/categories', headers=auth).json()['items'][0]
    assert client.put('/api/v1/categories/'+str(category['id']), headers=auth, json={'name':'Renomeada'}).status_code == 200
    result = sync(client, auth, since=before['revision'], epoch=before['epoch'])
    assert len(result['items']) == 1 and result['items'][0]['category'] == 'Renomeada'


def test_incremental_stock_sale_cancel_and_duplicate_no_new_changes(environment):
    client, _, auth, _, _ = setup(environment)
    row = client.post('/api/v1/products', headers=auth, json=product(sku='SYNC-SALE', stock='10', sale_price='10')).json()
    before = sync(client, auth)
    sale = sell(client, auth, [row], 'offline-sync-sale-key-001', [{'method':'cash','amount':'10'}])
    assert sale.status_code == 201, sale.text
    changed = sync(client, auth, since=before['revision'], epoch=before['epoch'])
    assert changed['items'][0]['stock'] == '9.000'
    assert sell(client, auth, [row], 'offline-sync-sale-key-001', [{'method':'cash','amount':'10'}]).status_code == 201
    assert sync(client, auth, since=changed['revision'], epoch=changed['epoch'])['items'] == []
    assert client.post('/api/v1/sales/'+str(sale.json()['id'])+'/cancel', headers=auth, json={'reason':'Teste sincronização'}).status_code == 200
    restored = sync(client, auth, since=changed['revision'], epoch=changed['epoch'])
    assert restored['items'][0]['stock'] == '10.000'
    row = restored['items'][0]
    response = client.post('/api/v1/inventory/adjustments', headers=auth, json={
        'idempotency_key':'offline-sync-stock-key-001','product_id':row['id'],
        'product_version':row['version'],'kind':'entry','quantity':'2','reason':'Sincronização estoque'})
    assert response.status_code == 201, response.text
    assert sync(client, auth, since=restored['revision'], epoch=restored['epoch'])['items'][0]['stock'] == '12.000'


def test_changed_snapshot_epoch_cursor_and_permissions(environment):
    client, _ = environment
    auth = credentials(environment)
    for i in range(3):
        assert client.post('/api/v1/products', headers=auth, json=product(sku='SYNC-PAGE-'+str(i))).status_code == 201
    first = sync(client, auth, limit=1)
    second = sync(client, auth, after_id=first['next_id'], revision=first['revision'], epoch=first['epoch'], limit=1)
    assert first['items'][0]['id'] != second['items'][0]['id']
    assert client.get(URL, headers=auth, params={'after_id':1}).status_code == 422
    for params in ({'since':first['revision']+1,'epoch':first['epoch']},
                   {'since':first['revision']}, {'since':1,'epoch':str(uuid4())}):
        assert client.get(URL, headers=auth, params=params).status_code == 409
    client.post('/api/v1/products', headers=auth, json=product(sku='SYNC-CHANGE'))
    assert client.get(URL, headers=auth, params={'after_id':first['next_id'],'revision':first['revision'],'epoch':first['epoch']}).status_code == 409
    assert client.get(URL).status_code == 401
    viewer = credentials(environment, 'viewer')
    assert client.get(URL, headers=viewer).status_code == 200
    assert client.get(URL, headers=auth, params={'limit':26}).status_code == 422


def test_offline_migration_preserves_prices_stock_and_existing_revision(tmp_path, monkeypatch):
    from pathlib import Path
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, select, text
    from sqlalchemy.orm import sessionmaker
    from app.models import Product, CatalogState
    from conftest import legacy_product
    from decimal import Decimal
    uri = 'sqlite:///' + str(tmp_path/'existing-offline.db')
    monkeypatch.setenv('DATABASE_URL', uri)
    config = Config()
    config.set_main_option('script_location', str(Path(__file__).resolve().parents[1]/'migrations'))
    command.upgrade(config, '007_reports')
    engine = create_engine(uri)
    factory = sessionmaker(bind=engine)
    with factory.begin() as db:
        legacy_product(db, sku='BEFORE-OFFLINE', name='Produto anterior', sale_price='190', cost_price='123', stock='2.500')
        db.execute(text('UPDATE catalog_state SET revision = 42 WHERE id = 1'))
    command.upgrade(config, 'head')
    with factory() as db:
        state = db.get(CatalogState, 1)
        epoch = state.epoch
        assert len(epoch) == 36 and state.revision == 42
        row = db.scalar(select(Product))
        assert row.sync_revision == 42 and row.stock == Decimal('2.500')
        assert row.sale_price == 190 and row.cost_price == 123
    command.upgrade(config, 'head')
    with factory() as db:
        assert db.get(CatalogState, 1).epoch == epoch
    engine.dispose()
