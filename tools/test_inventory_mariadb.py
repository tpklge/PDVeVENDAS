"""Inventory contention with sales in an isolated native MariaDB CI stack."""
import json
import os
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
if os.environ.get('CI') != 'true':
    raise SystemExit('Teste permitido apenas em CI isolado.')


def call(method,path,body=None,token=None):
    headers={'Content-Type':'application/json'}
    if token:headers['Authorization']='Bearer '+token
    req=urllib.request.Request('http://api:8000'+path,data=json.dumps(body).encode() if body is not None else None,headers=headers,method=method)
    try:response=urllib.request.urlopen(req,timeout=30)
    except urllib.error.HTTPError as error:response=error
    with response:
        raw=response.read()
        return response.status,json.loads(raw) if raw else None


token=call('POST','/api/v1/auth/login',{'username':'admin','password':'ci-isolated-only-password','device_id':'ci-inventory'})[1]['access_token']
assert call('POST','/api/v1/finance/cash/open',{'amount':'100','reason':'Fundo inicial CI','idempotency_key':'ci-open-cash-test_inventory_mariadb'},token)[0]==201

def create(sku,stock):
    code,row=call('POST','/api/v1/products',{'sku':sku,'name':'Estoque CI','sale_price':'190','stock':stock},token)
    assert code==201
    return row


def adjustment(product,key,kind='exit',quantity='1'):
    return {'product_id':product['id'],'product_version':product['version'],'kind':kind,
            'quantity':quantity,'reason':'Movimento CI isolado','idempotency_key':key}


def concurrent(requests):
    barrier=Barrier(2)
    def submit(item):
        path,body=item
        barrier.wait(timeout=10)
        return call('POST',path,body,token)
    with ThreadPoolExecutor(max_workers=2) as pool:return list(pool.map(submit,requests))


product=create('CI-INVENTORY-REPEAT','2')
body=adjustment(product,'ci-inventory-same-key-0001')
results=concurrent([('/api/v1/inventory/adjustments',body)]*2)
assert [c for c,_ in results]==[201,201],results
assert results[0][1]['id']==results[1][1]['id']
assert call('GET',f'/api/v1/inventory/{product["id"]}',token=token)[1]['stock']=='1.000'
assert call('POST','/api/v1/inventory/adjustments',{**body,'quantity':'2'},token)[0]==409
product=create('CI-INVENTORY-VS-SALE','1')
sale={'idempotency_key':'ci-sale-vs-inventory-0001','items':[{'product_id':product['id'],
      'product_version':product['version'],'expected_unit_price':'190','quantity':'1'}],
      'payments':[{'method':'cash','amount':'190'}]}
results=concurrent([('/api/v1/sales',sale),('/api/v1/inventory/adjustments',adjustment(product,'ci-inventory-vs-sale-0001'))])
assert sorted(c for c,_ in results)==[201,409],results
assert call('GET',f'/api/v1/inventory/{product["id"]}',token=token)[1]['stock']=='0.000'
history=call('GET',f'/api/v1/inventory/{product["id"]}/movements',token=token)[1]['items']
assert len(history)==2 and history[-1]['before']=='1.000' and history[-1]['after']=='0.000'
current=call('GET',f'/api/v1/inventory/{product["id"]}',token=token)[1]
assert call('POST','/api/v1/inventory/adjustments',adjustment(current,'ci-negative-stock-test-0001'),token)[0]==409
assert len(call('GET',f'/api/v1/inventory/{product["id"]}/movements',token=token)[1]['items'])==2
print('PASS: MariaDB — estoque idempotente, saída/venda simultâneas, saldo não negativo e histórico.')

key='ci-inventory-abandoned-0001'
assert call('POST',f'/api/v1/inventory/requests/{key}/resolve',token=token)[1]['state']=='abandoned'
assert call('POST','/api/v1/inventory/adjustments',adjustment(current,key,kind='entry'),token)[0]==409
key=body['idempotency_key']
result=call('POST',f'/api/v1/inventory/requests/{key}/resolve',token=token)[1]
assert result['state']=='completed' and result['movement']['after']=='1.000'
assert call('GET',f'/api/v1/inventory/movements/{result["movement"]["id"]}',token=token)[0]==200
print('PASS: recuperação de movimento confirmado e barreira contra envio tardio.')
