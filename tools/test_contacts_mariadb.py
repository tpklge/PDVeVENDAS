"""Contacts integration in isolated CI; no production credentials or personal data."""
import json
import os
import urllib.request
import urllib.error
if os.environ.get('CI') != 'true':
    raise SystemExit('Teste permitido apenas no CI isolado.')

def call(method,path,body=None,token=None,status=200):
    headers={'Content-Type':'application/json'}
    if token:headers['Authorization']='Bearer '+token
    request=urllib.request.Request('http://api:8000'+path,data=json.dumps(body).encode() if body is not None else None,headers=headers,method=method)
    try:response=urllib.request.urlopen(request,timeout=20)
    except urllib.error.HTTPError as error:response=error
    with response:
        assert response.status==status,f'{method}: HTTP {response.status}, esperado {status}'
        raw=response.read()
        return json.loads(raw) if raw else None

token=call('POST','/api/v1/auth/login',{'username':'admin','password':'ci-isolated-only-password','device_id':'ci-contacts'})['access_token']
for mod,kind,doc in (('customers','PF','52998224725'),('suppliers','PJ','12ABC34501DE35')):
    path='/api/v1/'+mod
    body={'name':'Cadastro fictício CI','person_type':kind,'document':doc}
    row=call('POST',path,body,token,201)
    call('POST',path,body,token,409)
    assert len(call('POST',path+'/search',{'document_query':doc},token)['items'])==1
    assert 'document' not in call('GET',path,token=token)['items'][0]
    updated=call('PUT',path+'/'+str(row['id']),{**body,'version':1,'name':'CI alterado'},token)
    assert updated['version']==2
    call('PUT',path+'/'+str(row['id']),{**body,'version':1},token,409)
    call('DELETE',path+'/'+str(row['id'])+'?version=2',token=token)
    assert not call('GET',path,token=token)['items']
    assert len(call('GET',path+'/'+str(row['id'])+'/history',token=token)['items'])==3
    call('PUT',path+'/'+str(row['id']),{**body,'version':3,'active':True},token)
    if mod=='suppliers':
        product=call('POST','/api/v1/products',{'sku':'CI-LINK','name':'Produto vínculo CI','sale_price':'190'},token,201)
        call('POST',path+'/'+str(row['id'])+'/products',{'product_id':product['id']},token,201)
        assert call('GET',path+'/'+str(row['id'])+'/products',token=token)['items'][0]['id']==product['id']
print('PASS: MariaDB real — clientes/fornecedores, documentos, pesquisa, versões, histórico e vínculos.')
