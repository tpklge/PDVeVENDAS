"""Incremental sync and response-loss retries, only on the disposable CI stack."""
import json
import os
import urllib.request
import urllib.error
if os.environ.get('CI') != 'true':
    raise SystemExit('Teste permitido apenas em CI isolado.')
token = None


def call(method, path, body=None):
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    request = urllib.request.Request('http://api:8000' + path, headers=headers,
        data=json.dumps(body).encode() if body is not None else None, method=method)
    try:
        response = urllib.request.urlopen(request, timeout=30)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        raw = response.read()
        return response.status, json.loads(raw) if raw else None


def login():
    global token
    token = call('POST', '/api/v1/auth/login', {'username': 'admin',
        'password': 'ci-isolated-only-password', 'device_id': 'ci-offline'})[1]['access_token']


login()
P = '/api/v1/sync/products'
code, first = call('GET', P+'?limit=1')
assert code == 200 and len(first['epoch']) == 36
if first['next_id']:
    code, second = call('GET', P+f'?limit=1&after_id={first["next_id"]}&revision={first["revision"]}&epoch={first["epoch"]}')
    assert code == 200 and second['items'][0]['id'] != first['items'][0]['id']
since = first['revision']
code, row = call('POST', '/api/v1/products', {'sku':'CI-OFFLINE', 'name':'Produto offline CI', 'sale_price':'190', 'stock':'10'})
assert code == 201
params = f'?since={since}&epoch={first["epoch"]}'
code, delta = call('GET', P+params)
assert code == 200 and len(delta['items']) == 1 and delta['items'][0]['id'] == row['id']
assert call('GET', P+f'?revision={since}&epoch={first["epoch"]}')[0] == 409
code, cash = call('POST', '/api/v1/finance/cash/open', {'amount':'0','reason':'Offline CI','idempotency_key':'ci-offline-cash-key-0001'})
assert code == 201
body = {'idempotency_key':'ci-offline-sale-key-0001','items':[{'product_id':row['id'],'product_version':row['version'],'quantity':'1','expected_unit_price':'190'}],'payments':[{'method':'cash','amount':'190'}]}
# Deliberately discard the result after the commit, emulating an unknown response.
assert call('POST','/api/v1/sales',body)[0] == 201
before_retry = call('GET', P)[1]['revision']
assert call('POST','/api/v1/auth/logout',{})[0] == 204
token = None
assert call('POST','/api/v1/sales',body)[0] == 401
login()
code, retry = call('POST','/api/v1/sales',body)
assert code == 201 and retry['replayed'] is True
code, again = call('POST','/api/v1/sales',body)
assert code == 201 and again['id'] == retry['id']
assert call('GET',P)[1]['revision'] == before_retry
current = call('GET','/api/v1/products/'+str(row['id']))[1]
assert current['stock'] == '9.000'
# A stale draft with another key is rejected, without adjusting stock.
assert call('POST','/api/v1/sales',{**body,'idempotency_key':'ci-offline-conflict-key-001'})[0] == 409
assert call('GET','/api/v1/products/'+str(row['id']))[1]['stock'] == '9.000'
assert call('DELETE','/api/v1/products/'+str(row['id'])+'?version='+str(current['version']))[0] == 204
code, inactive = call('GET',P+f'?since={before_retry}&epoch={first["epoch"]}')
assert code == 200 and inactive['items'][0]['active'] is False
print('PASS: catálogo incremental, cursor obsoleto, resposta descartada após commit, reautenticação, idempotência, conflito e inativação no MariaDB.')
