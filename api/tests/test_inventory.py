from decimal import Decimal
from sqlalchemy import select, func
from app.models import StockMovement, InventoryRequest, Product, AuditLog
from test_products import credentials, product


def prepare(environment):
    client,_ = environment
    auth = credentials(environment)
    row = client.post('/api/v1/products', headers=auth, json=product(stock='10')).json()
    return auth,row


def request(row, **changes):
    return {'product_id': row['id'], 'product_version': row['version'], 'kind': 'entry',
            'quantity': '2.500', 'reason': 'Recebimento teste',
            'idempotency_key': 'inventory-key-test-00001', **changes}


def test_entry_exit_count_history_and_retry(environment):
    client,factory = environment
    auth,row = prepare(environment)
    body = request(row)
    response = client.post('/api/v1/inventory/adjustments', headers=auth, json=body)
    assert response.status_code == 201,response.text
    entry = response.json()
    assert entry['before'] == '10.000' and entry['after'] == '12.500'
    replay = client.post('/api/v1/inventory/adjustments', headers=auth, json={**body,'quantity':'2.5'})
    assert replay.json()['replayed'] and replay.json()['id'] == entry['id']
    assert client.post('/api/v1/inventory/adjustments', headers=auth, json={**body,'quantity':'3'}).status_code == 409
    current = client.get(f'/api/v1/inventory/{row["id"]}', headers=auth).json()
    assert current['stock'] == '12.500' and current['version'] == 2
    exit_body = request(current,kind='exit',quantity='1.250',idempotency_key='inventory-key-test-00002')
    exit_row = client.post('/api/v1/inventory/adjustments', headers=auth, json=exit_body).json()
    assert exit_row['quantity'] == '-1.250' and exit_row['after'] == '11.250'
    current = client.get(f'/api/v1/inventory/{row["id"]}', headers=auth).json()
    adjustment = request(current,kind='adjustment',quantity=None,target_quantity='0',
                         reason='Contagem física teste',idempotency_key='inventory-key-test-00003')
    response = client.post('/api/v1/inventory/adjustments', headers=auth, json=adjustment)
    assert response.status_code == 201 and response.json()['after'] == '0.000'
    history = client.get(f'/api/v1/inventory/{row["id"]}/movements', headers=auth).json()['items']
    assert [item['after'] for item in history] == ['10.000','12.500','11.250','0.000']
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(InventoryRequest)) == 3
        assert db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.entity=='stock_movements')) == 3


def test_permissions_validation_stale_and_nonnegative_stock(environment):
    client,factory = environment
    auth,row = prepare(environment)
    viewer = credentials(environment,'viewer')
    assert client.get('/api/v1/inventory',headers=viewer).status_code == 200
    assert client.post('/api/v1/inventory/adjustments',headers=viewer,json=request(row)).status_code == 403
    assert client.get('/api/v1/inventory').status_code == 401
    for change,status in [({'kind':'exit','quantity':'11'},409),({'product_version':99},409),
                          ({'reason':' '},422),({'quantity':'1.0001'},422),
                          ({'kind':'adjustment','target_quantity':'1'},422),
                          ({'kind':'adjustment','quantity':None,'target_quantity':'10'},422),
                          ({'quantity':'999999999999.999'},409)]:
        assert client.post('/api/v1/inventory/adjustments',headers=auth,json=request(row,**change)).status_code == status
    with factory() as db:
        assert db.get(Product,row['id']).stock == Decimal('10')
        assert db.scalar(select(func.count()).select_from(InventoryRequest)) == 0
        assert db.scalar(select(func.count()).select_from(StockMovement)) == 1


def test_stock_low_snapshot_and_inactive_history(environment):
    client,_ = environment
    auth,row = prepare(environment)
    client.post('/api/v1/products',headers=auth,json=product(sku='LOW',stock='1',stock_min='2'))
    low = client.get('/api/v1/inventory?low_only=true',headers=auth).json()['items']
    assert len(low)==1 and low[0]['sku']=='LOW' and low[0]['stock_low']
    snapshot = client.get('/api/v1/inventory?limit=1',headers=auth).json()
    client.post('/api/v1/inventory/adjustments',headers=auth,json=request(row))
    assert client.get(f'/api/v1/inventory?revision={snapshot["revision"]}',headers=auth).status_code==409
    assert client.delete(f'/api/v1/products/{row["id"]}?version=2',headers=auth).status_code==204
    assert client.post('/api/v1/inventory/adjustments',headers=auth,json=request(row,product_version=3)).status_code==409
    assert len(client.get(f'/api/v1/inventory/{row["id"]}/movements',headers=auth).json()['items'])==2
    assert not client.get('/api/v1/inventory?q=%',headers=auth).json()['items']


def test_inventory_failure_rolls_back_balance_movement_request_and_audit(environment,monkeypatch):
    from app import inventory
    client,factory = environment
    auth,row = prepare(environment)
    original = inventory.record
    def fail(*args):raise RuntimeError('Injected audit failure')
    monkeypatch.setattr(inventory,'record',fail)
    try:
        client.post('/api/v1/inventory/adjustments',headers=auth,json=request(row))
    except RuntimeError:
        pass
    with factory() as db:
        assert db.get(Product,row['id']).stock==10 and db.get(Product,row['id']).version==1
        assert db.scalar(select(func.count()).select_from(InventoryRequest))==0
        assert db.scalar(select(func.count()).select_from(StockMovement))==1
    monkeypatch.setattr(inventory,'record',original)
    assert client.post('/api/v1/inventory/adjustments',headers=auth,json=request(row)).status_code==201


def test_sales_and_inventory_share_balance_and_revision(environment):
    client,_ = environment
    auth,row = prepare(environment)
    assert client.post("/api/v1/finance/cash/open",headers=auth,json={"amount":"100","reason":"Fundo inicial teste","idempotency_key":"inventory-open-cash-test-0001"}).status_code==201
    client.post('/api/v1/inventory/adjustments',headers=auth,json=request(row))
    current = client.get(f'/api/v1/products/{row["id"]}',headers=auth).json()
    sale = {'idempotency_key':'sale-after-inventory-0001','items':[{'product_id':row['id'],
            'product_version':current['version'],'quantity':'1','expected_unit_price':current['sale_price']}],
            'payments':[{'method':'cash','amount':current['sale_price']}]}
    assert client.post('/api/v1/sales',headers=auth,json=sale).status_code==201
    assert client.get(f'/api/v1/inventory/{row["id"]}',headers=auth).json()['stock']=='11.500'
    assert client.post('/api/v1/inventory/adjustments',headers=auth,
                       json=request(current,idempotency_key='stale-after-sale-0001')).status_code==409


def test_resolve_pending_attempt_prevents_late_movement_and_recovers_completed(environment):
    client,_ = environment
    auth,row = prepare(environment)
    body = request(row)
    key = body['idempotency_key']
    resolved = client.post(f'/api/v1/inventory/requests/{key}/resolve',headers=auth)
    assert resolved.status_code == 200 and resolved.json()['state']=='abandoned'
    assert client.post('/api/v1/inventory/adjustments',headers=auth,json=body).status_code==409
    assert client.get(f'/api/v1/inventory/{row["id"]}',headers=auth).json()['stock']=='10.000'
    assert client.post(f'/api/v1/inventory/requests/{key}/resolve',headers=auth).json()['state']=='abandoned'
    body['idempotency_key']='inventory-completed-key-0001'
    movement = client.post('/api/v1/inventory/adjustments',headers=auth,json=body).json()
    resolved = client.post(f'/api/v1/inventory/requests/{body["idempotency_key"]}/resolve',headers=auth).json()
    assert resolved['state']=='completed' and resolved['movement']['id']==movement['id']
    assert client.post('/api/v1/inventory/requests/invalid/resolve',headers=auth).status_code==422
    viewer = credentials(environment,'viewer')
    assert client.post(f'/api/v1/inventory/requests/{key}/resolve',headers=viewer).status_code==403
