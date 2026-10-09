"""Concurrent financial transactions against the isolated native MariaDB CI stack."""
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
    request=urllib.request.Request('http://api:8000'+path,data=json.dumps(body).encode() if body is not None else None,headers=headers,method=method)
    try:response=urllib.request.urlopen(request,timeout=30)
    except urllib.error.HTTPError as error:response=error
    with response:
        raw=response.read()
        return response.status,json.loads(raw) if raw else None

token=call('POST','/api/v1/auth/login',{'username':'admin','password':'ci-isolated-only-password','device_id':'ci-sales'})[1]['access_token']
assert call('POST','/api/v1/finance/cash/open',{'amount':'100','reason':'Fundo inicial CI','idempotency_key':'ci-open-cash-test_sales_mariadb'},token)[0]==201
def create(sku,stock):
    code,row=call('POST','/api/v1/products',{'sku':sku,'name':'Produto vendas CI','sale_price':'190','stock':stock},token)
    assert code==201
    return row

def body(product,key):
    return {'idempotency_key':key,'items':[{'product_id':product['id'],'product_version':product['version'],'expected_unit_price':product['sale_price'],'quantity':'1'}],
            'payments':[{'method':'cash','amount':'200'}]}

def concurrent(requests):
    barrier=Barrier(2)
    def submit(request):
        barrier.wait(timeout=10)
        return call('POST','/api/v1/sales',request,token)
    with ThreadPoolExecutor(max_workers=2) as pool:
        return list(pool.map(submit,requests))

product=create('CI-SALE-CONCURRENT','1')
results=concurrent([body(product,'ci-concurrent-sale-key-0001'),body(product,'ci-concurrent-sale-key-0002')])
assert sorted(code for code,_ in results)==[201,409],results
assert call('GET',f'/api/v1/products/{product["id"]}',token=token)[1]['stock']=='0.000'
product=create('CI-SALE-IDEMPOTENT','2')
request=body(product,'ci-idempotence-same-key-0001')
results=concurrent([request,request])
assert [code for code,_ in results]==[201,201],results
assert results[0][1]['id']==results[1][1]['id']
sale=results[0][1]
assert sale['change']=='10.00' and sale['total']=='190.00'
assert call('GET',f'/api/v1/products/{product["id"]}',token=token)[1]['stock']=='1.000'
for _ in range(2):
    code,canceled=call('POST',f'/api/v1/sales/{sale["id"]}/cancel',{'reason':'Cancelamento CI'},token)
    assert code==200 and canceled['status']=='canceled'
assert call('GET',f'/api/v1/products/{product["id"]}',token=token)[1]['stock']=='2.000'
product=create('CI-SALE-PAYMENT-FAIL','1')
request={**body(product,'ci-payment-invalid-key-0001'),'payments':[{'method':'pix','amount':'200'}]}
assert call('POST','/api/v1/sales',request,token)[0]==422
assert call('GET',f'/api/v1/products/{product["id"]}',token=token)[1]['stock']=='1.000'
key='ci-resolve-abandon-key-0001'
assert call('POST',f'/api/v1/sales/requests/{key}/resolve',token=token)[1]['state']=='abandoned'
assert call('POST','/api/v1/sales',body(product,key),token)[0]==409
print('PASS: MariaDB — concorrência de estoque, idempotência simultânea, troco, cancelamento e barreira de recuperação.')
