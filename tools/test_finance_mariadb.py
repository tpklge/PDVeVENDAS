"""Cash races against real isolated MariaDB on both native CI architectures."""
import json
import os
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
if os.environ.get('CI')!='true':raise SystemExit('Teste permitido apenas em CI isolado.')

def call(method,path,body=None,token=None):
    headers={'Content-Type':'application/json'}
    if token:headers['Authorization']='Bearer '+token
    req=urllib.request.Request('http://api:8000'+path,data=json.dumps(body).encode() if body is not None else None,headers=headers,method=method)
    try:response=urllib.request.urlopen(req,timeout=30)
    except urllib.error.HTTPError as error:response=error
    with response:
        raw=response.read();return response.status,json.loads(raw) if raw else None

token=call('POST','/api/v1/auth/login',{'username':'admin','password':'ci-isolated-only-password','device_id':'ci-finance'})[1]['access_token']
P='/api/v1/finance'
def post(path,body):return call('POST',path,body,token)
def get(path):return call('GET',path,token=token)[1]
def concurrent(requests):
    barrier=Barrier(2)
    def submit(pair):
        barrier.wait(timeout=10);return post(*pair)
    with ThreadPoolExecutor(max_workers=2) as pool:return list(pool.map(submit,requests))

opening={'amount':'100','reason':'Fundo caixa CI','idempotency_key':'ci-finance-opening-key-0001'}
results=concurrent([(P+'/cash/open',opening)]*2)
assert [c for c,_ in results]==[201,201],results
session=results[0][1]
assert results[1][1]['id']==session['id']
assert post(P+'/cash/open',{**opening,'idempotency_key':'ci-finance-opening-key-0002'})[0]==409
move={'amount':'60','kind':'withdraw','reason':'Retirada concorrente CI','session_id':session['id'],'idempotency_key':'ci-finance-withdraw-key-001'}
results=concurrent([(P+'/cash/movements',move),(P+'/cash/movements',{**move,'idempotency_key':'ci-finance-withdraw-key-002'})])
assert sorted(c for c,_ in results)==[201,409],results
assert get(P+'/cash/current')['session']['expected_cash']=='40.00'
move.update(kind='deposit',amount='10',idempotency_key='ci-finance-repeat-key-0001')
results=concurrent([(P+'/cash/movements',move)]*2)
assert [c for c,_ in results]==[201,201] and results[0][1]['id']==results[1][1]['id'],results
assert get(P+'/cash/current')['session']['expected_cash']=='50.00'
category=post(P+'/categories',{'kind':'receivable','name':'Receita CI','idempotency_key':'ci-finance-category-key-001'})[1]
account=post(P+'/accounts',{'kind':'receivable','category_id':category['id'],'description':'Conta concorrente CI','due_date':'2026-10-08','amount':'80','idempotency_key':'ci-finance-account-key-001'})[1]
settle={'account_id':account['id'],'version':1,'session_id':session['id'],'amount':'50','method':'cash','reason':'Recebimento manual CI','idempotency_key':'ci-finance-settle-key-0001'}
results=concurrent([(P+'/settlements',settle),(P+'/settlements',{**settle,'idempotency_key':'ci-finance-settle-key-0002'})])
assert sorted(c for c,_ in results)==[201,409],results
assert get(P+'/accounts/'+str(account['id']))['paid']=='50.00'
assert get(P+'/cash/current')['session']['expected_cash']=='100.00'
key='ci-finance-abandoned-key-001'
assert post(P+'/requests/'+key+'/resolve',None)[1]['state']=='abandoned'
assert post(P+'/cash/movements',{**move,'idempotency_key':key})[0]==409
resolved=post(P+'/requests/'+move['idempotency_key']+'/resolve',None)[1]
assert resolved['state']=='completed' and resolved['result']['id']>0
# Concurrent sale/close: sale must either be included in the close revision or refused.
product=post('/api/v1/products',{'sku':'CI-FINANCE-SALE-CLOSE','name':'Venda versus fechamento CI','sale_price':'10','stock':'1'})[1]
current=get(P+'/cash/current')['session']
close={'session_id':session['id'],'last_movement_id':current['last_movement_id'],'amount':'100','reason':'Contagem conferida CI','idempotency_key':'ci-finance-close-key-00001'}
sale={'idempotency_key':'ci-finance-sale-key-00001','items':[{'product_id':product['id'],'product_version':product['version'],'expected_unit_price':'10','quantity':'1'}],'payments':[{'method':'cash','amount':'10'}]}
results=concurrent([(P+'/cash/close',close),('/api/v1/sales',sale)])
assert [c for c,_ in results] in ([200,409],[409,201]),results
if results[0][0]==409:
    current=get(P+'/cash/current')['session'];close.update(last_movement_id=current['last_movement_id'],amount='110')
    assert post(P+'/cash/close',close)[0]==200
closed=get(P+'/cash/sessions/'+str(session['id']))
assert closed['status']=='closed' and closed['difference']=='0.00'
assert closed['expected_cash']==('110.00' if results[1][0]==201 else '100.00')
assert get('/api/v1/products/'+str(product['id']))['stock']==('0.000' if results[1][0]==201 else '1.000')
assert post(P+'/cash/close',close)[1]['replayed']
print('PASS: MariaDB — abertura única, replay simultâneo, sangria sem saldo negativo, baixa concorrente, fechamento versus venda e barreiras de recuperação.')
