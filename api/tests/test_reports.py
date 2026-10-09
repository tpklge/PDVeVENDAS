from datetime import datetime
from decimal import Decimal
from sqlalchemy import select
from app.models import Sale, Product, User
from app.finance_models import CashMovement
from test_products import credentials, product
from test_finance import setup, account

P='/api/v1/reports/'
def get(client,auth,kind,**params):
    return client.get(P+kind,headers=auth,params={'from_date':'2026-10-01','to_date':'2026-10-31',**params})
def sell(client,auth,products,key,payments,discount='0'):
    return client.post('/api/v1/sales',headers=auth,json={'idempotency_key':key,'discount_amount':discount,'items':[{'product_id':r['id'],'product_version':r['version'],'quantity':'1','expected_unit_price':r['sale_price']} for r in products],'payments':payments})

def test_sale_seller_payment_totals_change_no_join_multiplication(environment):
    client,factory,auth,_,_=setup(environment)
    rows=[client.post('/api/v1/products',headers=auth,json=product(sku='REP-'+str(i),stock='10',sale_price='10')).json() for i in range(2)]
    sale=sell(client,auth,rows,'reports-sale-key-000001',[{'method':'cash','amount':'10'},{'method':'cash','amount':'5'},{'method':'pix','amount':'10'}])
    assert sale.status_code==201,sale.text
    for kind in ('sales','sellers','payments'):
        report=get(client,auth,kind)
        assert report.status_code==200,report.text
        assert report.json()['summary']['sales']==1 and report.json()['summary']['total']=='20.00'
    payments=get(client,auth,'payments').json()['rows']
    assert {r[0]:r[2] for r in payments}=={'cash':'10.00','pix':'10.00'}
    assert get(client,auth,'cash').json()['summary']['cash_net']=='10.00'
    assert client.post(f'/api/v1/sales/{sale.json()["id"]}/cancel',headers=auth,json={'reason':'Cancelamento relatório'}).status_code==200
    assert get(client,auth,'sales').json()['summary']['total']=='0.00'
    assert get(client,auth,'cancellations').json()['summary']['total']=='20.00'
    assert get(client,auth,'cash').json()['summary']['cash_net']=='0.00'

def test_product_allocation_discount_rounding_and_historical_price(environment):
    client,factory,auth,_,_=setup(environment)
    rows=[client.post('/api/v1/products',headers=auth,json=product(sku='ROUND-'+str(i),stock='10',sale_price='0.01')).json() for i in range(3)]
    sale=sell(client,auth,rows,'reports-rounding-key-0001',[{'method':'cash','amount':'0.02'}],discount='0.01')
    assert sale.status_code==201,sale.text
    report=get(client,auth,'products');assert report.status_code==200,report.text
    report=report.json()
    assert sum(Decimal(r[4]) for r in report['rows'])==Decimal('0.02')
    assert all(Decimal(r[4])<=Decimal('0.01') for r in report['rows'])
    assert report['summary']['total']=='0.02' and report['summary']['products']==3
    with factory.begin() as db:db.get(Product,rows[0]['id']).sale_price=Decimal('123')
    assert get(client,auth,'products').json()['summary']['total']=='0.02'
    assert get(client,auth,'products',product_id=rows[0]['id']).json()['rows_total']==1

def test_period_cuiaba_boundaries_filters_and_empty_reports(environment):
    client,factory,auth,_,_=setup(environment)
    row=client.post('/api/v1/products',headers=auth,json=product(stock='10',sale_price='10')).json()
    sale=sell(client,auth,[row],'reports-boundary-key-0001',[{'method':'cash','amount':'10'}]).json()
    with factory.begin() as db:db.get(Sale,sale['id']).created_at=datetime(2026,10,10,3,59,59)
    assert get(client,auth,'sales',from_date='2026-10-09',to_date='2026-10-09').json()['summary']['sales']==1
    assert get(client,auth,'sales',from_date='2026-10-10',to_date='2026-10-10').json()['summary']['sales']==0
    with factory.begin() as db:db.get(Sale,sale['id']).created_at=datetime(2026,10,10,4)
    assert get(client,auth,'sales',from_date='2026-10-09',to_date='2026-10-09').json()['summary']['sales']==0
    assert get(client,auth,'sales',operator_id=99999).json()['summary']['total']=='0.00'
    for params in ({'from_date':'2026-11-01','to_date':'2026-10-01'},{'from_date':'2024-01-01','to_date':'2026-01-01'},{'from_date':'2026-02-30'},{'limit':26},{'offset':1}):
        assert get(client,auth,'sales',**params).status_code==422

def test_stock_pagination_revision_financial_changes_and_permissions(environment):
    client,factory,auth,session,_=setup(environment)
    for i in range(3):client.post('/api/v1/products',headers=auth,json=product(sku='STOCK-'+str(i),stock='1',stock_min='2'))
    viewer=credentials(environment,'viewer')
    first=get(client,viewer,'low-stock',limit=1).json()
    assert first['rows_total']==3 and first['next_offset']==1
    second=get(client,viewer,'low-stock',offset=1,limit=1,revision=first['revision'])
    assert second.status_code==200 and second.json()['rows'][0][0]!=first['rows'][0][0]
    assert 'cost_price' not in str(first) and 'sale_price' not in str(first)
    for kind in ('sales','sellers','products','payments','cash','receivables','payables','cancellations'):
        assert get(client,viewer,kind).status_code==403
    client.post('/api/v1/finance/cash/movements',headers=auth,json={'session_id':session['id'],'kind':'deposit','amount':'1','reason':'Revisão relatório','idempotency_key':'reports-deposit-key-0001'})
    assert get(client,viewer,'low-stock',offset=1,limit=1,revision=first['revision']).status_code==409
    assert get(client,viewer,'stock',operator_id=1).status_code==422
    assert client.get(P+'stock').status_code==401

def test_account_due_period_partial_totals_and_changed_filter_revision(environment):
    client,_,auth,session,_=setup(environment)
    row,_=account(client,auth)
    client.post('/api/v1/finance/settlements',headers=auth,json={'account_id':row['id'],'version':1,'session_id':session['id'],'method':'cash','amount':'30','reason':'Baixa relatório','idempotency_key':'reports-settle-key-0001'})
    data=get(client,auth,'receivables').json()
    assert data['summary']['original']=='80.00' and data['summary']['paid']=='30.00' and data['summary']['remaining']=='50.00'
    assert get(client,auth,'receivables',from_date='2026-10-02').json()['rows_total']==0
    assert get(client,auth,'receivables',only_open=True,revision=data['revision']).status_code==409
    assert get(client,auth,'payables').json()['summary']['remaining']=='0.00'

def test_cash_sessions_closed_snapshot_aggregate_and_permissions(environment):
    client,_,auth,session,_=setup(environment)
    row=client.post('/api/v1/products',headers=auth,json=product(stock='2',sale_price='10')).json()
    assert sell(client,auth,[row],'reports-close-sale-key-001',[{'method':'cash','amount':'10'}]).status_code==201
    current=client.get('/api/v1/finance/cash/current',headers=auth).json()['session']
    assert client.post('/api/v1/finance/cash/close',headers=auth,json={'session_id':session['id'],'last_movement_id':current['last_movement_id'],'amount':'109','reason':'Diferença relatório','idempotency_key':'reports-close-cash-key-001'}).status_code==200
    response=get(client,auth,'cash-sessions');assert response.status_code==200,response.text
    summary=response.json()['summary']
    assert summary['closed_expected']=='110.00' and summary['closed_counted']=='109.00' and summary['closed_difference']=='-1.00'
    assert response.json()['rows'][0][5:] == ['110.00','109.00','-1.00']
    assert get(client,credentials(environment,'viewer'),'cash-sessions').status_code==403
