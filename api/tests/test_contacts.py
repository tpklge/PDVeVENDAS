from sqlalchemy import select
from app.models import User, Role, Permission, Contact, AuditLog
from app.security import hasher
from conftest import PASSWORD
from test_products import credentials


def test_contacts_crud_history_and_documents(environment):
    client, factory = environment
    headers = credentials(environment)
    for path, kind, document in (("customers","PF","529.982.247-25"),("suppliers","PJ","12.ABC.345/01DE-35")):
        body = {"name":"João Teste", "person_type":kind, "document":document,"email":"teste@example.com","postal_code":"78000-000","state":"mt"}
        response = client.post('/api/v1/'+path, headers=headers, json=body)
        assert response.status_code == 201, response.text
        row = response.json()
        assert row['state'] == 'MT' and row['postal_code'] == '78000000'
        assert client.post('/api/v1/'+path, headers=headers, json=body).status_code == 409
        assert 'document' not in client.get('/api/v1/'+path, headers=headers).json()['items'][0]
        found = client.post('/api/v1/'+path+'/search', headers=headers, json={"document_query":document}).json()['items']
        assert len(found) == 1
        updated = client.put(f'/api/v1/{path}/{row["id"]}', headers=headers, json={**body,'name':'Nome alterado','version':1})
        assert updated.status_code == 200
        assert client.put(f'/api/v1/{path}/{row["id"]}', headers=headers, json={**body,'version':1}).status_code == 409
        assert client.delete(f'/api/v1/{path}/{row["id"]}?version=2', headers=headers).status_code == 200
        assert not client.get('/api/v1/'+path,headers=headers).json()['items']
        history=client.get(f'/api/v1/{path}/{row["id"]}/history',headers=headers).json()
        assert len(history['items']) == 3 and history['purchases_available'] is (path == 'customers')
        assert client.put(f'/api/v1/{path}/{row["id"]}',headers=headers,json={**body,'version':3,'active':True}).status_code == 200
    for bad in ('11111111111','52998224724','text'):
        assert client.post('/api/v1/customers',headers=headers,json={'name':'x','document':bad}).status_code == 422
    assert client.post('/api/v1/suppliers',headers=headers,json={'name':'x','person_type':'PJ','document':'12ABC34501DE34'}).status_code == 422
    assert client.post('/api/v1/suppliers',headers=headers,json={'name':'x'}).status_code == 422
    assert client.post('/api/v1/customers/search',headers=headers,json={'document_query':'invalid'}).status_code == 422
    for invalid in ({'state':'ZZ'},{'postal_code':'x'},{'email':'bad'},{'name':' '},{'notes':'bad\ntext'}):
        assert client.post('/api/v1/customers',headers=headers,json={'name':'x',**invalid}).status_code == 422
    with factory() as db:
        for row in db.scalars(select(AuditLog).where(AuditLog.entity.in_(['customers','suppliers']))):
            assert '529' not in row.entity_id and '@' not in row.operation


def test_contacts_rbac_hidden_documents_and_links(environment):
    client,factory=environment
    admin=credentials(environment)
    body={'name':'Pessoa','document':'52998224725'}
    customer=client.post('/api/v1/customers',headers=admin,json=body).json()
    with factory.begin() as db:
        perms=list(db.scalars(select(Permission).where(Permission.code.in_(['customers.read','customers.update']))))
        role=Role(name='Editor sem documentos',permissions=perms)
        db.add(User(username='editor',password_hash=hasher.hash(PASSWORD),must_change_password=False,roles=[role]))
    editor=credentials(environment,'editor')
    row=client.get(f'/api/v1/customers/{customer["id"]}',headers=editor).json()
    assert row['document'] is None and row['has_document'] and not row['document_editable']
    assert client.post('/api/v1/customers/search',headers=editor,json={'document_query':body['document']}).status_code==403
    assert client.put(f'/api/v1/customers/{row["id"]}',headers=editor,json={'name':'Editado','version':1}).status_code==200
    assert client.get(f'/api/v1/customers/{row["id"]}',headers=admin).json()['document']=='52998224725'
    assert client.put(f'/api/v1/customers/{row["id"]}',headers=editor,json={'name':'Editado','version':2,'active':False}).status_code==403
    assert client.get('/api/v1/suppliers',headers=editor).status_code==403
    supplier=client.post('/api/v1/suppliers',headers=admin,json={'name':'Fornecedor','person_type':'PJ'}).json()
    product=client.post('/api/v1/products',headers=admin,json={'name':'Produto','sku':'LINK1','sale_price':'190'}).json()
    url=f'/api/v1/suppliers/{supplier["id"]}/products'
    for _ in range(2):assert client.post(url,headers=admin,json={'product_id':product['id']}).status_code==201
    assert len(client.get(url,headers=admin).json()['items'])==1
    assert client.delete(url+'/'+str(product['id']),headers=admin).status_code==204
    assert not client.get(url,headers=admin).json()['items']
    with factory() as db:assert db.scalar(select(Contact).where(Contact.id==customer['id'])) is not None


def test_contacts_pagination_minimization(environment):
    client,_=environment
    admin=credentials(environment)
    for i in range(3):assert client.post('/api/v1/customers',headers=admin,json={'name':f'Café {i}'}).status_code==201
    page=client.post('/api/v1/customers/search',headers=admin,json={'limit':2,'q':'Café'}).json()
    assert len(page['items'])==2 and page['next_id']
    assert set(page['items'][0])=={'id','name','person_type','trade_name','active','version','has_document'}
    next_page=client.post('/api/v1/customers/search',headers=admin,json={'limit':2,'after_id':page['next_id']}).json()
    assert len(next_page['items'])==1 and next_page['next_id'] is None


def test_upgrade_preserves_previous_users_products_and_roles(tmp_path, monkeypatch):
    from pathlib import Path
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.models import Product
    from app.seed import CODES
    from app.security import verify
    uri='sqlite:///'+str(tmp_path/'upgrade.db')
    monkeypatch.setenv('DATABASE_URL',uri)
    config=Config(str(Path(__file__).resolve().parents[1]/'alembic.ini'))
    config.set_main_option('script_location',str(Path(__file__).resolve().parents[1]/'migrations'))
    command.upgrade(config,'002_products')
    engine=create_engine(uri)
    factory=sessionmaker(bind=engine)
    old_codes=[c for c in CODES if not c.startswith('suppliers.') and c not in ('customers.documents','customers.delete')]
    with factory.begin() as db:
        permissions=[Permission(code=c) for c in old_codes]
        admin_role=Role(name='Administrador',permissions=permissions)
        custom=Role(name='Personalizado',permissions=[permissions[0]])
        db.add_all([admin_role,custom,User(username='original',password_hash=hasher.hash(PASSWORD),roles=[admin_role],must_change_password=False)])
        from conftest import legacy_product
        legacy_product(db,sku='EXISTING',name='Produto existente',sale_price='190',cost_price='123',stock=0,stock_min=0)
    command.upgrade(config,'head')
    command.upgrade(config,'head')
    with factory() as db:
        user=db.scalar(select(User).where(User.username=='original'))
        assert verify(user.password_hash,PASSWORD) and not user.must_change_password
        assert db.scalar(select(Product).where(Product.sku=='EXISTING')).sale_price==190
        assert 'suppliers.documents' in {p.code for r in user.roles for p in r.permissions}
        assert len(db.scalar(select(Role).where(Role.name=='Personalizado')).permissions)==1
    engine.dispose()



def test_document_and_postal_errors_identify_fields_without_personal_values(environment):
    client,_=environment
    headers=credentials(environment)
    response=client.post('/api/v1/customers',headers=headers,json={'name':'Teste','document':'52998224724','postal_code':'123'})
    assert response.status_code==422
    message=response.json()['error']['message']
    assert 'CPF/CNPJ' in message and 'CEP' in message
    assert '52998224724' not in message and 'campos informados' not in message
    assert client.post('/api/v1/customers',headers=headers,json={'name':'Sem documento','postal_code':''}).status_code==201
