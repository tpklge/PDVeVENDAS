from decimal import Decimal
from sqlalchemy import select, func
from app.models import Sale, SaleItem, SalePayment, StockMovement, Product, Role, User, Permission
from app.security import hasher
from conftest import PASSWORD
from test_products import credentials, product


def prepare(environment, **changes):
    client,_=environment
    auth=credentials(environment)
    assert client.post("/api/v1/finance/cash/open",headers=auth,json={"amount":"100","reason":"Fundo inicial teste","idempotency_key":"sales-open-cash-test-0001"}).status_code==201
    row=client.post('/api/v1/products',headers=auth,json=product(stock='10',sale_price='190',**changes)).json()
    body={'idempotency_key':'test-sale-unique-key-0001','items':[{'product_id':row['id'],'product_version':row['version'],'expected_unit_price':row['sale_price'],'quantity':'1'}], 'payments':[{'method':'cash','amount':'200'}]}
    return auth,row,body


def test_sale_stock_payments_idempotence_history_cancel(environment):
    client,factory=environment
    auth,product_row,body=prepare(environment)
    customer=client.post('/api/v1/customers',headers=auth,json={'name':'Cliente teste'}).json()
    body['customer_id']=customer['id']
    quote=client.post('/api/v1/sales/quote',headers=auth,json={k:v for k,v in body.items() if k not in ('payments','idempotency_key')})
    assert quote.status_code==200 and quote.json()['total']=='190.00'
    response=client.post('/api/v1/sales',headers=auth,json=body)
    assert response.status_code==201,response.text
    sale=response.json()
    assert sale['change']=='10.00' and sale['total']=='190.00' and sale['fiscal'] is False
    assert sale['payments'][0]['status']=='declared'
    repeat=client.post('/api/v1/sales',headers=auth,json=body)
    assert repeat.json()['id']==sale['id'] and repeat.json()['replayed']
    normalized={**body,'payments':[{'method':'cash','amount':'200.00'}]}
    assert client.post('/api/v1/sales',headers=auth,json=normalized).json()['replayed']
    assert client.post('/api/v1/sales',headers=auth,json={**body,'payments':[{'method':'cash','amount':'201'}]}).status_code==409
    after=client.get('/api/v1/products/'+str(product_row['id']),headers=auth).json()
    assert after['stock']=='9.000' and after['version']==2
    assert client.get(f'/api/v1/customers/{customer["id"]}/purchases',headers=auth).json()['items'][0]['id']==sale['id']
    assert client.delete(f'/api/v1/customers/{customer["id"]}?version=1',headers=auth).status_code==200
    assert client.get(f'/api/v1/customers/{customer["id"]}/purchases',headers=auth).json()['items'][0]['total']=='190.00'
    cancel=client.post(f'/api/v1/sales/{sale["id"]}/cancel',headers=auth,json={'reason':'Teste de cancelamento'})
    assert cancel.status_code==200 and cancel.json()['status']=='canceled' and not cancel.json()['external_refund_confirmed']
    assert client.post(f'/api/v1/sales/{sale["id"]}/cancel',headers=auth,json={'reason':'Repetição'}).json()['replayed']
    assert client.get('/api/v1/products/'+str(product_row['id']),headers=auth).json()['stock']=='10.000'
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(Sale))==1
        assert db.scalar(select(func.count()).select_from(StockMovement).where(StockMovement.sale_id==sale['id']))==2
        assert db.scalar(select(SalePayment)).status=='managerial_reversal'


def test_no_partial_sale_invalid_payment_stock_version_or_customer(environment):
    client,factory=environment
    auth,row,body=prepare(environment)
    changes=[{'items':[{**body['items'][0],'quantity':'11'}]}, {'payments':[{'method':'pix','amount':'200'}]},
        {'payments':[{'method':'cash','amount':'1'}]}, {'customer_id':999}, {'items':[{**body['items'][0],'expected_unit_price':'123'}]}]
    for change in changes:
        assert client.post('/api/v1/sales',headers=auth,json={**body,**change}).status_code in (409,422)
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(Sale))==0
        assert db.scalar(select(func.count()).select_from(SaleItem))==0
        assert db.scalar(select(Product)).stock==10
        assert db.scalar(select(func.count()).select_from(StockMovement).where(StockMovement.kind=='sale'))==0
    assert client.post('/api/v1/sales',headers=auth,json={**body,'items':[body['items'][0],body['items'][0]]}).status_code==422
    assert client.post('/api/v1/sales',headers=auth,json={**body,'payments':[{'method':'card','amount':'190','cvv':'123'}]}).status_code==422


def test_discounts_mixed_payment_rbac_and_price_snapshot(environment):
    client,factory=environment
    auth,row,body=prepare(environment)
    with factory.begin() as db:
        role=Role(name='Operador vendas',permissions=list(db.scalars(select(Permission).where(Permission.code.in_(['sales.read','sales.create','products.read'])))))
        db.add(User(username='seller',password_hash=hasher.hash(PASSWORD),must_change_password=False,roles=[role]))
    seller=credentials(environment,'seller')
    discounted={**body,'discount_percent':'10','payments':[{'method':'pix','amount':'100'},{'method':'cash','amount':'80'}]}
    assert client.post('/api/v1/sales',headers=seller,json=discounted).status_code==403
    response=client.post('/api/v1/sales',headers=auth,json=discounted)
    assert response.status_code==201,response.text
    sale=response.json()
    assert sale['total']=='171.00' and sale['discount']=='19.00' and sale['change']=='9.00'
    assert client.post(f'/api/v1/sales/{sale["id"]}/cancel',headers=seller,json={'reason':'Tentativa'}).status_code==403
    after=client.get('/api/v1/products/'+str(row['id']),headers=auth).json()
    edited=client.put('/api/v1/products/'+str(row['id']),headers=auth,json=product(stock='9',sale_price='200',version=after['version']))
    assert edited.status_code==200
    assert client.get('/api/v1/sales/'+str(sale['id']),headers=auth).json()['items'][0]['unit_price']=='190.00'
    assert client.get('/api/v1/sales',headers=credentials(environment,'viewer')).status_code==403


def test_transaction_rolls_back_on_write_failure(environment,monkeypatch):
    client,factory=environment
    auth,row,body=prepare(environment)
    import app.sales as module
    original=module.record
    def fail(*args,**kwargs):raise RuntimeError('simulated transaction failure')
    monkeypatch.setattr(module,'record',fail)
    # Failure is sanitized; the transaction must still roll back completely.
    assert client.post('/api/v1/sales',headers=auth,json=body).status_code == 500
    with factory() as db:
        assert db.scalar(select(Product)).stock==10
        assert db.scalar(select(func.count()).select_from(Sale))==0
        assert db.scalar(select(func.count()).select_from(SalePayment))==0
        assert db.scalar(select(func.count()).select_from(StockMovement).where(StockMovement.kind=='sale'))==0
    monkeypatch.setattr(module,'record',original)
    assert client.post('/api/v1/sales',headers=auth,json=body).status_code==201


def test_resolve_closes_key_before_late_request_and_preserves_committed_sale(environment):
    client,factory=environment
    auth,row,body=prepare(environment)
    path='/api/v1/sales/requests/'+body['idempotency_key']+'/resolve'
    assert client.post(path,headers=auth).json()['state']=='abandoned'
    assert client.post('/api/v1/sales',headers=auth,json=body).status_code==409
    with factory() as db:assert db.scalar(select(func.count()).select_from(Sale))==0
    body['idempotency_key']='other-key-confirmed-0001'
    sale=client.post('/api/v1/sales',headers=auth,json=body).json()
    resolved=client.post('/api/v1/sales/requests/'+body['idempotency_key']+'/resolve',headers=auth).json()
    assert resolved['state']=='completed' and resolved['sale']['id']==sale['id']
    assert client.post('/api/v1/sales',headers=auth,json=body).json()['replayed']


def test_incremental_sales_migration_preserves_contacts_and_opening_stock(tmp_path, monkeypatch):
    from alembic import command
    from alembic.config import Config
    from pathlib import Path
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.models import Contact, SaleRequest
    from app.security import verify
    uri='sqlite:///'+str(tmp_path/'existing-sales.db')
    config=Config()
    monkeypatch.setenv('DATABASE_URL',uri)
    config.set_main_option('script_location',str(Path(__file__).resolve().parents[1]/'migrations'))
    command.upgrade(config,'003_contacts')
    engine=create_engine(uri)
    factory=sessionmaker(bind=engine)
    with factory.begin() as db:
        db.add(User(username='original',password_hash=hasher.hash(PASSWORD),must_change_password=False))
        from conftest import legacy_product
        legacy_product(db,sku='BEFORE-PDV',name='Produto anterior',sale_price='190',cost_price='123',stock='2.500',stock_min=0)
        db.add(Contact(kind='customer',name='Cliente anterior',person_type='PF',document=None))
    command.upgrade(config,'head')
    command.upgrade(config,'head')
    with factory() as db:
        assert verify(db.scalar(select(User)).password_hash,PASSWORD)
        assert db.scalar(select(Contact)).name=='Cliente anterior'
        product_row=db.scalar(select(Product))
        assert product_row.stock==Decimal('2.500') and product_row.sale_price==190
        opening=db.scalar(select(StockMovement))
        assert opening.kind=='opening' and opening.before==0 and opening.after==Decimal('2.500')
        assert db.scalar(select(func.count()).select_from(SaleRequest))==0
    engine.dispose()
