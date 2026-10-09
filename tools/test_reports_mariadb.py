"""Reporting invariants against native MariaDB, never production."""
import json
import os
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo
import urllib.request
import urllib.error
if os.environ.get('CI')!='true':raise SystemExit('Teste permitido apenas em CI isolado.')
def call(method,path,body=None):
    headers={'Content-Type':'application/json'}
    if token:headers['Authorization']='Bearer '+token
    req=urllib.request.Request('http://api:8000'+path,data=json.dumps(body).encode() if body is not None else None,headers=headers,method=method)
    try:response=urllib.request.urlopen(req,timeout=30)
    except urllib.error.HTTPError as error:response=error
    with response:
        raw=response.read();return response.status,json.loads(raw) if raw else None

token=None
token=call('POST','/api/v1/auth/login',{'username':'admin','password':'ci-isolated-only-password','device_id':'ci-reports'})[1]['access_token']
today=datetime.now(ZoneInfo('America/Cuiaba')).date().isoformat()
P='/api/v1/reports/'
def report(kind,extra=''):
    code,data=call('GET',P+kind+'?from_date='+today+'&to_date='+today+extra)
    assert code==200,(kind,code,data)
    return data
baseline=Decimal(report('sales')['summary']['total'])
before_cash=Decimal(next((r[2] for r in report('payments')['rows'] if r[0]=='cash'),'0'))
code,session=call('POST','/api/v1/finance/cash/open',{'amount':'100','reason':'Fundo relatórios CI','idempotency_key':'ci-reports-open-key-0001'})
assert code==201,(code,session)
products=[]
for i in range(3):
    code,row=call('POST','/api/v1/products',{'sku':'CI-REPORT-'+str(i),'name':'Produto relatório CI','sale_price':'0.01','stock':'10'})
    assert code==201;products.append(row)
body={'idempotency_key':'ci-reports-sale-key-0001','discount_amount':'0.01','items':[{'product_id':r['id'],'product_version':r['version'],'quantity':'1','expected_unit_price':'0.01'} for r in products],'payments':[{'method':'cash','amount':'0.02'},{'method':'cash','amount':'0.03'}]}
code,sale=call('POST','/api/v1/sales',body);assert code==201,(code,sale)
assert Decimal(report('sales')['summary']['total'])==baseline+Decimal('0.02')
assert Decimal(next(r[2] for r in report('payments')['rows'] if r[0]=='cash'))==before_cash+Decimal('0.02')
net=[]
for row in products:
    data=report('products','&product_id='+str(row['id']))
    assert data['rows_total']==1
    value=Decimal(data['rows'][0][4]);assert value<=Decimal('0.01')
    net.append(value)
assert sum(net)==Decimal('0.02'),net
first=report('stock','&limit=1')
assert first['next_offset']==1
code,_=call('GET',P+'stock?limit=1&offset=1&revision='+first['revision'])
assert code==200
call('POST','/api/v1/finance/cash/movements',{'session_id':session['id'],'kind':'deposit','amount':'1','reason':'Revisão relatório CI','idempotency_key':'ci-reports-deposit-key-001'})
assert call('GET',P+'stock?limit=1&offset=1&revision='+first['revision'])[0]==409
current=call('GET','/api/v1/finance/cash/current')[1]['session']
assert call('POST','/api/v1/finance/cash/close',{'session_id':session['id'],'last_movement_id':current['last_movement_id'],'amount':'101.01','reason':'Diferença de um centavo CI','idempotency_key':'ci-reports-close-key-0001'})[0]==200
cash=report('cash-sessions')
row=next(r for r in cash['rows'] if r[0]==str(session['id']))
assert row[5:] == ['101.02','101.01','-0.01'],row
# Verify cents near the monetary limit using large fractional quantity.
assert call('POST','/api/v1/finance/cash/open',{'amount':'0','reason':'Novo caixa limites CI','idempotency_key':'ci-reports-large-open-key-001'})[0]==201
code,large=call('POST','/api/v1/products',{'sku':'CI-REPORT-LARGE','name':'Limite decimal CI','sale_price':'9999999999.99','stock':'100'})
assert code==201
body={'idempotency_key':'ci-reports-large-sale-key-001','discount_amount':'0.01','items':[{'product_id':large['id'],'product_version':large['version'],'quantity':'99.999','expected_unit_price':large['sale_price']}],'payments':[{'method':'pix','amount':'999989999998.99'}]}
code,large_sale=call('POST','/api/v1/sales',body);assert code==201,(code,large_sale)
assert report('products','&product_id='+str(large['id']))['summary']['total']==large_sale['total']
assert report('cancellations')['summary']['external_refund_confirmed'] is False
print('PASS: MariaDB reports — aggregate sales, cash net of change, largest-remainder cents, large decimal limit, revisions and immutable close snapshots.')
