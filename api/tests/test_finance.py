from sqlalchemy import select, func
import pytest
from app.finance_models import CashSession, CashMovement, FinancialAccount, FinancialSettlement, FinanceRequest
from test_products import credentials, product

P='/api/v1/finance'
def setup(environment,opening='100'):
    client,factory=environment;auth=credentials(environment)
    body={'amount':opening,'reason':'Fundo inicial','idempotency_key':'finance-open-test-key-0001'}
    response=client.post(P+'/cash/open',headers=auth,json=body)
    assert response.status_code==201,response.text
    return client,factory,auth,response.json(),body

def test_cash_open_moves_close_immutable_snapshot_and_replay(environment):
    client,factory,auth,session,opening=setup(environment)
    assert client.post(P+'/cash/open',headers=auth,json={**opening,'amount':'100.00'}).json()['replayed']
    assert client.post(P+'/cash/open',headers=auth,json={**opening,'idempotency_key':'duplicate-opening-key-0001'}).status_code==409
    body={'session_id':session['id'],'amount':'50','kind':'deposit','reason':'Troco adicional','idempotency_key':'cash-deposit-test-key-0001'}
    move=client.post(P+'/cash/movements',headers=auth,json=body)
    assert move.status_code==201,move.text
    assert client.post(P+'/cash/movements',headers=auth,json=body).json()['replayed']
    assert client.post(P+'/cash/movements',headers=auth,json={**body,'amount':'51'}).status_code==409
    withdraw={**body,'kind':'withdraw','amount':'20','idempotency_key':'cash-withdraw-test-key-001'}
    assert client.post(P+'/cash/movements',headers=auth,json=withdraw).status_code==201
    current=client.get(P+'/cash/current',headers=auth).json()['session']
    assert current['expected_cash']=='130.00' and current['deposits']=='50.00' and current['withdrawals']=='20.00'
    close={'session_id':session['id'],'amount':'129','reason':'Diferença na contagem','last_movement_id':0,'idempotency_key':'cash-close-test-key-00001'}
    assert client.post(P+'/cash/close',headers=auth,json=close).status_code==409
    close['last_movement_id']=current['last_movement_id']
    closed=client.post(P+'/cash/close',headers=auth,json=close)
    assert closed.status_code==200,closed.text
    assert closed.json()['difference']=='-1.00'
    assert client.post(P+'/cash/close',headers=auth,json=close).json()['replayed']
    assert client.post(P+'/cash/movements',headers=auth,json={**body,'idempotency_key':'closed-cash-move-key-0001'}).status_code==409
    assert client.get(P+'/cash/current',headers=auth).json()['session'] is None
    history=client.get(P+'/cash/sessions',headers=auth).json()['items']
    assert history[0]['expected_cash']=='130.00' and history[0]['difference']=='-1.00'
    assert len(client.get(f'{P}/cash/sessions/{session["id"]}/movements',headers=auth).json()['items'])==2

def account(client,auth,kind='receivable'):
    category=client.post(P+'/categories',headers=auth,json={'kind':kind,'name':'Categoria teste','idempotency_key':'category-'+kind+'-key-0001'}).json()
    body={'kind':kind,'category_id':category['id'],'description':'Conta de teste','due_date':'2026-10-01','amount':'80','idempotency_key':'account-'+kind+'-key-0001'}
    response=client.post(P+'/accounts',headers=auth,json=body)
    assert response.status_code==201,response.text
    return response.json(),body

def test_receivable_partial_settlement_overpayment_and_payable_cash(environment):
    client,factory,auth,session,_=setup(environment)
    row,body=account(client,auth)
    assert client.post(P+'/accounts',headers=auth,json=body).json()['replayed']
    pay={'account_id':row['id'],'version':1,'session_id':session['id'],'method':'pix','amount':'30','reason':'Pix conferido pelo operador','idempotency_key':'settlement-test-key-00001'}
    response=client.post(P+'/settlements',headers=auth,json=pay)
    assert response.status_code==201,response.text
    assert response.json()['account']['paid']=='30.00'
    assert client.post(P+'/settlements',headers=auth,json=pay).json()['replayed']
    assert client.post(P+'/settlements',headers=auth,json={**pay,'amount':'51','version':2,'idempotency_key':'settlement-overpay-key-001'}).status_code==422
    assert client.post(P+'/settlements',headers=auth,json={**pay,'idempotency_key':'settlement-stale-key-0001'}).status_code==409
    pay.update(version=2,amount='50',method='cash',idempotency_key='settlement-test-key-00002')
    assert client.post(P+'/settlements',headers=auth,json=pay).json()['account']['status']=='paid'
    payable,_=account(client,auth,'payable')
    pay.update(account_id=payable['id'],version=1,amount='80',idempotency_key='payable-test-key-0000001')
    assert client.post(P+'/settlements',headers=auth,json=pay).status_code==201
    current=client.get(P+'/cash/current',headers=auth).json()['session']
    assert current['expected_cash']=='70.00' and current['by_method']['pix']=='30.00'
    assert len(client.get(f'{P}/accounts/{row["id"]}/settlements',headers=auth).json()['items'])==2
    assert not client.get(P+'/accounts?kind=receivable&only_open=true',headers=auth).json()['items']
    assert len(client.get(P+'/accounts?kind=receivable&from_date=2026-10-01&to_date=2026-10-01',headers=auth).json()['items'])==1
    assert client.get(P+'/accounts?kind=receivable&from_date=2026-10-02&to_date=2026-10-01',headers=auth).status_code==422

def test_sales_cash_change_cancel_and_closed_history(environment):
    client,factory,auth,session,_=setup(environment)
    row=client.post('/api/v1/products',headers=auth,json=product(stock='10',sale_price='190')).json()
    sale_body={'idempotency_key':'finance-sale-test-key-0001','items':[{'product_id':row['id'],'product_version':1,'quantity':'1','expected_unit_price':'190'}],'payments':[{'method':'pix','amount':'100'},{'method':'cash','amount':'100'}]}
    sale=client.post('/api/v1/sales',headers=auth,json=sale_body)
    assert sale.status_code==201,sale.text
    assert client.post('/api/v1/sales',headers=auth,json=sale_body).json()['replayed']
    current=client.get(P+'/cash/current',headers=auth).json()['session']
    assert current['expected_cash']=='190.00' and current['by_method']['pix']=='100.00' and current['sales_total']=='190.00'
    closed=client.post(P+'/cash/close',headers=auth,json={'session_id':session['id'],'last_movement_id':current['last_movement_id'],'amount':'190','reason':'Contagem conferida','idempotency_key':'finance-close-key-0000001'}).json()
    assert client.post('/api/v1/sales',headers=auth,json={**sale_body,'idempotency_key':'no-cash-sale-key-00001','items':[{**sale_body['items'][0],'product_version':2}]}).status_code==409
    assert client.post(f'/api/v1/sales/{sale.json()["id"]}/cancel',headers=auth,json={'reason':'Devolução autorizada'}).status_code==409
    client.post(P+'/cash/open',headers=auth,json={'amount':'100','reason':'Novo turno caixa','idempotency_key':'finance-new-cash-key-0001'})
    assert client.post(f'/api/v1/sales/{sale.json()["id"]}/cancel',headers=auth,json={'reason':'Devolução autorizada'}).status_code==200
    assert client.get(f'{P}/cash/sessions/{session["id"]}',headers=auth).json()=={k:v for k,v in closed.items() if k!='replayed'}
    assert client.get(P+'/cash/current',headers=auth).json()['session']['expected_cash']=='10.00'
    with factory() as db:assert db.scalar(select(func.count()).select_from(CashMovement).where(CashMovement.kind=='sale'))==2

def test_cash_permissions_device_scope_validation_and_retry_barrier(environment):
    client,factory,auth,session,_=setup(environment)
    viewer=credentials(environment,'viewer')
    for path in ['/cash/current','/accounts?kind=receivable','/categories?kind=receivable']:
        assert client.get(P+path,headers=viewer).status_code==403
    assert client.post(P+'/cash/open',headers=viewer,json={'amount':'0','reason':'Teste acesso','idempotency_key':'viewer-open-key-000001'}).status_code==403
    second=client.post('/api/v1/auth/login',json={'username':'admin','password':'testing-only-password-0123456789','device_id':'other-device'}).json()
    other={'Authorization':'Bearer '+second['access_token']}
    assert client.get(f'{P}/cash/sessions/{session["id"]}',headers=other).status_code==404
    body={'session_id':session['id'],'kind':'withdraw','amount':'101','reason':'Retirada teste','idempotency_key':'bad-withdraw-test-key-001'}
    assert client.post(P+'/cash/movements',headers=auth,json=body).status_code==409
    assert client.post(P+'/cash/movements',headers=auth,json={**body,'amount':'0.001'}).status_code==422
    key='abandoned-finance-key-001'
    assert client.post(P+'/requests/'+key+'/resolve',headers=auth).json()['state']=='abandoned'
    assert client.post(P+'/cash/movements',headers=auth,json={**body,'amount':'1','idempotency_key':key}).status_code==409
    ok={**body,'kind':'deposit','amount':'1','idempotency_key':'completed-finance-key-001'}
    result=client.post(P+'/cash/movements',headers=auth,json=ok).json()
    assert client.post(P+'/requests/'+ok['idempotency_key']+'/resolve',headers=auth).json()['result']['id']==result['id']
    # Role revocation must also protect financial results recovered by key.
    _,account_body=account(client,auth)
    from app.models import User, Role, Permission
    with factory.begin() as db:
        limited=Role(name='Caixa limitado',permissions=[db.scalar(select(Permission).where(Permission.code=='cash.open'))])
        db.add(limited)
        db.scalar(select(User).where(User.username=='admin')).roles=[limited]
    assert client.post(P+'/requests/'+account_body['idempotency_key']+'/resolve',headers=auth).status_code==403
    assert client.post(P+'/requests/'+ok['idempotency_key']+'/resolve',headers=auth).status_code==200

def test_finance_atomic_rollback_on_audit_failure(environment,monkeypatch):
    client,factory,auth,session,_=setup(environment)
    row,_=account(client,auth)
    import app.finance as module
    def fail(*args):raise RuntimeError('injected audit failure')
    monkeypatch.setattr(module,'record',fail)
    body={'account_id':row['id'],'version':1,'session_id':session['id'],'method':'cash','amount':'80','reason':'Baixa integral','idempotency_key':'rollback-settle-key-00001'}
    with pytest.raises(RuntimeError):client.post(P+'/settlements',headers=auth,json=body)
    with factory() as db:
        assert db.get(FinancialAccount,row['id']).paid==0
        assert db.scalar(select(func.count()).select_from(FinancialSettlement))==0
        assert db.scalar(select(func.count()).select_from(CashMovement))==0
        assert not db.scalar(select(FinanceRequest).where(FinanceRequest.idempotency_key==body['idempotency_key']))

def test_cash_migration_preserves_historical_sales_without_inventing_receipts(tmp_path,monkeypatch):
    from pathlib import Path
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.models import User, Product, Sale, SaleItem, SalePayment
    from app.security import hasher, verify
    from conftest import PASSWORD
    uri='sqlite:///'+str(tmp_path/'existing-cash.db')
    monkeypatch.setenv('DATABASE_URL',uri)
    config=Config();config.set_main_option('script_location',str(Path(__file__).resolve().parents[1]/'migrations'))
    command.upgrade(config,'005_inventory')
    engine=create_engine(uri);factory=sessionmaker(bind=engine)
    with factory.begin() as db:
        user=User(username='existing-admin',password_hash=hasher.hash(PASSWORD),must_change_password=False)
        from conftest import legacy_product
        db.add(user);db.flush()
        product_id=legacy_product(db,sku='BEFORE-CASH',name='Produto histórico',sale_price='190',cost_price='123',stock='9',stock_min=0)
        sale=Sale(user_id=user.id,device_id='old-terminal',idempotency_key='historical-sale-key-00001',request_hash='0'*64,subtotal='190',discount='0',total='190',tendered='200',change='10')
        db.add(sale);db.flush()
        db.add(SaleItem(sale_id=sale.id,product_id=product_id,sku='BEFORE-CASH',name='Produto histórico',quantity='1',unit_price='190',discount='0',subtotal='190'))
        db.add(SalePayment(sale_id=sale.id,method='cash',amount='200'))
    command.upgrade(config,'head');command.upgrade(config,'head')
    with factory() as db:
        assert verify(db.scalar(select(User)).password_hash,PASSWORD)
        assert db.scalar(select(Product)).stock==9
        assert db.scalar(select(Sale)).total==190 and db.scalar(select(Sale)).change==10
        assert db.scalar(select(SalePayment)).status=='declared'
        assert db.scalar(select(func.count()).select_from(CashSession))==0
        assert db.scalar(select(func.count()).select_from(CashMovement))==0
    engine.dispose()
