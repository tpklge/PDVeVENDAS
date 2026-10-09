"""Server-calculated sale, serialized inventory transaction and idempotent retries."""
import hashlib
import json
from decimal import Decimal, ROUND_HALF_UP
from typing import Annotated, Literal
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import Field, model_validator, field_validator
from sqlalchemy import select
from .dependencies import Db, Input, Current, allowed
from .models import Sale, SaleRequest, SaleItem, SalePayment, StockMovement, Product, Contact, User, utcnow
from .products import lock_catalog, record

router=APIRouter(prefix='/api/v1/sales',tags=['sales'])
Read=Annotated[User,Depends(allowed('sales.read'))]
Create=Annotated[User,Depends(allowed('sales.create'))]
Cancel=Annotated[User,Depends(allowed('sales.cancel'))]
Money=Annotated[Decimal,Field(ge=0,max_digits=14,decimal_places=2)]
Percent=Annotated[Decimal,Field(ge=0,le=100,max_digits=5,decimal_places=2)]

class Item(Input):
    product_id:int=Field(ge=1)
    product_version:int=Field(ge=1)
    quantity:Decimal=Field(gt=0,max_digits=15,decimal_places=3)
    expected_unit_price:Decimal=Field(ge=0,max_digits=12,decimal_places=2)
    discount_amount:Money=Decimal('0')
    discount_percent:Percent=Decimal('0')

    @model_validator(mode='after')
    def single_discount(self):
        if self.discount_amount and self.discount_percent:raise ValueError('Escolha desconto em valor ou percentual')
        return self

class Cart(Input):
    customer_id:int|None=Field(default=None,ge=1)
    items:list[Item]=Field(min_length=1,max_length=20)
    discount_amount:Money=Decimal('0')
    discount_percent:Percent=Decimal('0')

    @model_validator(mode='after')
    def validate_cart(self):
        if self.discount_amount and self.discount_percent:raise ValueError('Escolha desconto total em valor ou percentual')
        if len({i.product_id for i in self.items})!=len(self.items):raise ValueError('Produto repetido: ajuste a quantidade')
        return self

class Payment(Input):
    method:Literal['cash','pix','debit','credit','transfer','other']
    amount:Decimal=Field(gt=0,max_digits=14,decimal_places=2)

class Finish(Cart):
    idempotency_key:str=Field(min_length=16,max_length=64,pattern=r'^[A-Za-z0-9_-]+$')
    payments:list[Payment]=Field(min_length=0,max_length=6)

class Cancellation(Input):
    reason:str=Field(min_length=3,max_length=240)
    @field_validator('reason')
    @classmethod
    def reason_value(cls,value):
        value=value.strip()
        if len(value)<3 or any(ord(c)<32 for c in value):raise ValueError('Informe justificativa válida')
        return value

def cents(value):return value.quantize(Decimal('0.01'),rounding=ROUND_HALF_UP)
def decimal_text(value):return format(value,'.2f')
def discount_limit(user):
    codes={p.code for r in user.roles for p in r.permissions}
    if 'sales.discount' not in codes:return Decimal(0)
    names={r.name for r in user.roles}
    return Decimal(100 if 'Administrador' in names else 20 if 'Gerente' in names else 10)

def calculate(db,body,user):
    if body.customer_id:
        customer=db.scalar(select(Contact).where(Contact.id==body.customer_id).with_for_update())
        if not customer or customer.kind!='customer' or not customer.active:raise HTTPException(409,'Cliente não encontrado ou inativo.')
    ids=sorted(i.product_id for i in body.items)
    products={p.id:p for p in db.scalars(select(Product).where(Product.id.in_(ids)).order_by(Product.id).with_for_update())}
    lines=[];gross=Decimal(0);line_discounts=Decimal(0);limit=discount_limit(user)
    for item in body.items:
        product=products.get(item.product_id)
        if not product or not product.active:raise HTTPException(409,'Produto não encontrado ou inativo. Atualize o carrinho.')
        if product.version!=item.product_version or product.sale_price!=item.expected_unit_price:raise HTTPException(409,'Preço/cadastro/estoque alterado. Atualize o carrinho e confirme os novos valores.')
        if product.stock<item.quantity:raise HTTPException(409,f'Estoque insuficiente para SKU {product.sku}.')
        subtotal=cents(product.sale_price*item.quantity)
        if subtotal>Decimal('999999999999.99'):raise HTTPException(422,'Valor do item excede o limite.')
        discount=cents(item.discount_amount or subtotal*item.discount_percent/100)
        if discount>subtotal:raise HTTPException(422,'Desconto excede o valor do item.')
        if discount>cents(subtotal*limit/100):raise HTTPException(403,'Desconto do item excede o limite do perfil. Solicite usuário autorizado.')
        lines.append({'product':product,'quantity':item.quantity,'unit_price':product.sale_price,'discount':discount,'subtotal':subtotal-discount})
        gross+=subtotal;line_discounts+=discount
    net=gross-line_discounts
    global_discount=cents(body.discount_amount or net*body.discount_percent/100)
    total=net-global_discount
    if total<0:raise HTTPException(422,'Desconto total excede o valor da venda.')
    overall_discount=line_discounts+global_discount
    if overall_discount>cents(gross*limit/100):raise HTTPException(403,'Desconto acumulado excede o limite do perfil. Solicite usuário autorizado.')
    if gross>Decimal('999999999999.99'):raise HTTPException(422,'Valor da venda excede o limite.')
    return lines,gross,overall_discount,total

def quote_payload(lines,gross,discount,total,user):
    return {'items':[{'product_id':line['product'].id,'sku':line['product'].sku,'name':line['product'].name,
        'quantity':format(line['quantity'],'.3f'),'unit_price':decimal_text(line['unit_price']),
        'discount':decimal_text(line['discount']),'subtotal':decimal_text(line['subtotal'])} for line in lines],
        'subtotal':decimal_text(gross),'discount':decimal_text(discount),'total':decimal_text(total),'discount_limit_percent':decimal_text(discount_limit(user))}

def serialize(sale,detail=True):
    out={'id':sale.id,'status':sale.status,'customer_id':sale.customer_id,'operator_id':sale.user_id,'device_id':sale.device_id,
        'created_at':sale.created_at.isoformat()+'Z','canceled_at':sale.canceled_at.isoformat()+'Z' if sale.canceled_at else None,
        'payment_confirmation':'operator_declared','external_refund_confirmed':False,'fiscal':False}
    out.update({key:decimal_text(getattr(sale,key)) for key in ('subtotal','discount','total','tendered','change')})
    if detail:
        out['cancel_reason']=sale.cancel_reason
        out['items']=[{'product_id':i.product_id,'sku':i.sku,'name':i.name,'quantity':format(i.quantity,'.3f'),
            'unit_price':decimal_text(i.unit_price),'discount':decimal_text(i.discount),'subtotal':decimal_text(i.subtotal)} for i in sale.items]
        out['payments']=[{'method':p.method,'amount':decimal_text(p.amount),'status':p.status} for p in sale.payments]
    return out

def fingerprint(body):
    data=body.model_dump(mode='json',exclude={'idempotency_key'})
    for item in data['items']:
        for key in ('quantity','expected_unit_price','discount_amount','discount_percent'):item[key]=str(Decimal(item[key]).normalize())
    for key in ('discount_amount','discount_percent'):data[key]=str(Decimal(data[key]).normalize())
    for p in data['payments']:p['amount']=str(Decimal(p['amount']).normalize())
    return hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()

@router.post('/quote')
def quote(body:Cart,user:Create,db:Db):
    lock_catalog(db)
    return quote_payload(*calculate(db,body,user),user)

@router.post('',status_code=201)
def finish(body:Finish,user:Create,current:Current,db:Db,request:Request):
    state=lock_catalog(db)
    device=current[0].device_id
    decision=db.scalar(select(SaleRequest).where(SaleRequest.user_id==user.id,SaleRequest.device_id==device,SaleRequest.idempotency_key==body.idempotency_key).with_for_update())
    if decision and decision.state=='abandoned':raise HTTPException(409,'Tentativa encerrada pelo operador. Gere nova tentativa após revisar o carrinho.')
    previous=db.scalar(select(Sale).where(Sale.user_id==user.id,Sale.device_id==device,Sale.idempotency_key==body.idempotency_key).with_for_update())
    hashed=fingerprint(body)
    if previous:
        if previous.request_hash!=hashed:raise HTTPException(409,'Chave de idempotência já usada com outra venda.')
        return {**serialize(previous),'replayed':True}
    lines,gross,discount,total=calculate(db,body,user)
    paid=sum((p.amount for p in body.payments),Decimal(0))
    noncash=sum((p.amount for p in body.payments if p.method!='cash'),Decimal(0))
    cash=paid-noncash
    if paid<total:raise HTTPException(422,'Pagamento insuficiente.')
    if noncash>total or paid-total>cash:raise HTTPException(422,'Troco permitido somente sobre dinheiro; ajuste os pagamentos.')
    if paid>Decimal('999999999999.99'):raise HTTPException(422,'Pagamento excede o limite.')
    sale=Sale(user_id=user.id,device_id=device,idempotency_key=body.idempotency_key,request_hash=hashed,
        customer_id=body.customer_id,subtotal=gross,discount=discount,total=total,tendered=paid,change=paid-total)
    db.add(sale);db.flush()
    for line in lines:
        product=line['product'];before=product.stock;product.stock-=line['quantity'];product.version+=1;product.updated_at=utcnow();product.sync_revision=state.revision+1
        db.add(SaleItem(sale_id=sale.id,product_id=product.id,sku=product.sku,name=product.name,
            quantity=line['quantity'],unit_price=line['unit_price'],discount=line['discount'],subtotal=line['subtotal']))
        db.add(StockMovement(product_id=product.id,sale_id=sale.id,user_id=user.id,kind='sale',quantity=-line['quantity'],
            before=before,after=product.stock,reason='Saída por venda'))
    for payment in body.payments:db.add(SalePayment(sale_id=sale.id,method=payment.method,amount=payment.amount))
    db.add(SaleRequest(user_id=user.id,device_id=device,idempotency_key=body.idempotency_key,state='completed',sale_id=sale.id))
    db.flush();db.refresh(sale)
    from .finance import ledger_sale
    ledger_sale(db,sale,user,device)
    state.revision+=1
    record(db,request,user,'sales.create','sales',sale.id)
    db.commit()
    db.refresh(sale)
    return {**serialize(sale),'replayed':False}

@router.get('')
def list_sales(user:Read,db:Db,after_id:int=Query(0,ge=0),limit:int=Query(8,ge=1,le=25),customer_id:int|None=Query(None,ge=1)):
    query=select(Sale).where(Sale.id>after_id)
    if customer_id:query=query.where(Sale.customer_id==customer_id)
    rows=db.scalars(query.order_by(Sale.id).limit(limit+1)).all()
    return {'items':[serialize(s,False) for s in rows[:limit]],'next_id':rows[limit-1].id if len(rows)>limit else None}

@router.post('/requests/{key}/resolve')
def resolve(key:str,user:Create,current:Current,db:Db,request:Request):
    import re
    if not re.fullmatch(r'[A-Za-z0-9_-]{16,64}',key):raise HTTPException(422,'Identificador inválido.')
    lock_catalog(db)
    device=current[0].device_id
    decision=db.scalar(select(SaleRequest).where(SaleRequest.user_id==user.id,SaleRequest.device_id==device,SaleRequest.idempotency_key==key).with_for_update())
    sale=db.scalar(select(Sale).where(Sale.user_id==user.id,Sale.device_id==device,Sale.idempotency_key==key).with_for_update())
    if sale:return {'state':'completed','sale':serialize(sale)}
    if not decision:
        decision=SaleRequest(user_id=user.id,device_id=device,idempotency_key=key,state='abandoned')
        db.add(decision);db.flush()
        record(db,request,user,'sales.resolve','sale_requests',decision.id)
        db.commit()
    return {'state':'abandoned'}

@router.get('/{identity}')
def detail(identity:int,user:Read,db:Db):
    sale=db.get(Sale,identity)
    if not sale:raise HTTPException(404,'Venda não encontrada.')
    return serialize(sale)

@router.post('/{identity}/cancel')
def cancel(identity:int,body:Cancellation,user:Cancel,current:Current,db:Db,request:Request):
    state=lock_catalog(db)
    sale=db.scalar(select(Sale).where(Sale.id==identity).with_for_update())
    if not sale:raise HTTPException(404,'Venda não encontrada.')
    if sale.status=='canceled':return {**serialize(sale),'replayed':True}
    products={p.id:p for p in db.scalars(select(Product).where(Product.id.in_([i.product_id for i in sale.items])).order_by(Product.id).with_for_update())}
    for item in sale.items:
        product=products[item.product_id];before=product.stock
        if before+item.quantity>Decimal('999999999999.999'):raise HTTPException(409,'Reposição excede limite de estoque. Operação não aplicada.')
        product.stock+=item.quantity;product.version+=1;product.updated_at=utcnow();product.sync_revision=state.revision+1
        db.add(StockMovement(product_id=product.id,sale_id=sale.id,user_id=user.id,kind='cancellation',quantity=item.quantity,
            before=before,after=product.stock,reason=body.reason))
    sale.status='canceled';sale.canceled_by=user.id;sale.canceled_at=utcnow();sale.cancel_reason=body.reason
    for payment in sale.payments:payment.status='managerial_reversal'
    from .finance import ledger_cancel
    ledger_cancel(db,sale,user,current[0].device_id,body.reason)
    state.revision+=1
    record(db,request,user,'sales.cancel','sales',sale.id)
    db.commit();db.refresh(sale)
    return {**serialize(sale),'replayed':False}
