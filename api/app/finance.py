"""Serialized cash ledger, exact totals, manual accounts and durable retry barriers."""
import hashlib
import json
import re
from datetime import date
from decimal import Decimal
from typing import Annotated, Literal
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import Field, field_validator
from sqlalchemy import select, func
from .dependencies import Db, Input, Current, allowed
from .models import User, Contact, utcnow
from .finance_models import CashSession, CashMovement, FinancialCategory, FinancialAccount, FinancialSettlement, FinanceRequest
from .products import lock_catalog, record

router=APIRouter(prefix='/api/v1/finance',tags=['cash-finance'])
Money=Annotated[Decimal,Field(ge=0,max_digits=14,decimal_places=2)]
Kind=Literal['receivable','payable']
Method=Literal['cash','pix','debit','credit','transfer','other']
Read=Annotated[User,Depends(allowed('reports.financial'))]

def codes(user):return {p.code for r in user.roles for p in r.permissions}
def cash_access(current: Current):
    if not codes(current[1]) & {'cash.open','cash.close','cash.deposit','cash.withdraw','reports.financial'}:
        raise HTTPException(403,'Seu perfil não permite consultar caixa.')
    return current[1]
CashRead=Annotated[User,Depends(cash_access)]

def clean(value):
    value=value.strip()
    if len(value)<3 or any(ord(c)<32 for c in value):raise ValueError('Informe texto com pelo menos 3 caracteres')
    return value
class Mutation(Input):
    idempotency_key:str=Field(min_length=16,max_length=64,pattern=r'^[A-Za-z0-9_-]+$')
class Opening(Mutation):
    amount:Money
    reason:str=Field(min_length=3,max_length=240)
    _clean=field_validator('reason')(clean)
class Move(Opening):
    kind:Literal['deposit','withdraw']
    session_id:int=Field(ge=1)
class Closing(Opening):
    session_id:int=Field(ge=1)
    last_movement_id:int=Field(ge=0)
class Category(Mutation):
    kind:Kind
    name:str=Field(min_length=3,max_length=80)
    _clean=field_validator('name')(clean)
class Account(Mutation):
    kind:Kind
    category_id:int=Field(ge=1)
    contact_id:int|None=Field(default=None,ge=1)
    description:str=Field(min_length=3,max_length=240)
    due_date:date=Field(ge=date(1000,1,1))
    amount:Annotated[Decimal,Field(gt=0,max_digits=14,decimal_places=2)]
    _clean=field_validator('description')(clean)
class Settlement(Opening):
    account_id:int=Field(ge=1)
    version:int=Field(ge=1)
    session_id:int=Field(ge=1)
    method:Method

def money(value):return format(value,'.2f')
def permission(user,code):
    if code not in codes(user):raise HTTPException(403,'Seu perfil não permite esta operação.')
def current_cash(db,user,device,required=True):
    row=db.scalar(select(CashSession).where(CashSession.user_id==user.id,CashSession.device_id==device,CashSession.status=='open').with_for_update())
    if not row and required:raise HTTPException(409,'Abra o caixa em Caixa / Financeiro antes de registrar a operação.')
    return row

def totals(db,row):
    grouped=db.execute(select(CashMovement.kind,CashMovement.method,func.sum(CashMovement.amount)).where(CashMovement.cash_session_id==row.id).group_by(CashMovement.kind,CashMovement.method)).all()
    methods={m:Decimal(0) for m in ('cash','pix','debit','credit','transfer','other')}
    incoming=Decimal(0);outgoing=Decimal(0);sales=Decimal(0);settlements=Decimal(0)
    for kind,method,amount in grouped:
        methods[method]+=amount
        if kind=='deposit':incoming+=amount
        if kind=='withdraw':outgoing-=amount
        if kind in ('sale','sale_reversal'):sales+=amount
        if kind=='settlement':settlements+=amount
    expected=row.opening+methods['cash']
    last=db.scalar(select(func.max(CashMovement.id)).where(CashMovement.cash_session_id==row.id)) or 0
    return {'opening':money(row.opening),'sales_total':money(sales),'settlements_total':money(settlements),'deposits':money(incoming),'withdrawals':money(outgoing),'by_method':{k:money(v) for k,v in methods.items()},'expected_cash':money(expected),'last_movement_id':last}

def session_payload(db,row):
    summary=json.loads(row.snapshot) if row.status=='closed' else totals(db,row)
    return {'id':row.id,'operator_id':row.user_id,'device_id':row.device_id,'status':row.status,'note':row.note,'created_at':row.created_at.isoformat()+'Z','closed_at':row.closed_at.isoformat()+'Z' if row.closed_at else None,'counted':money(row.counted) if row.counted is not None else None,'difference':money(row.counted-Decimal(summary['expected_cash'])) if row.counted is not None else None,'close_reason':row.close_reason,**summary}

def account_payload(db,row):
    category=db.get(FinancialCategory,row.category_id)
    return {'id':row.id,'kind':row.kind,'category_id':row.category_id,'category':category.name,'contact_id':row.contact_id,'description':row.description,'due_date':row.due_date.isoformat(),'amount':money(row.amount),'paid':money(row.paid),'remaining':money(row.amount-row.paid),'status':'paid' if row.paid==row.amount else 'partial' if row.paid else 'open','overdue':row.due_date<utcnow().date() and row.paid<row.amount,'version':row.version,'created_at':row.created_at.isoformat()+'Z'}

def move_payload(row):
    return {'id':row.id,'session_id':row.cash_session_id,'operator_id':row.user_id,'sale_id':row.sale_id,'settlement_id':row.settlement_id,'kind':row.kind,'method':row.method,'amount':money(row.amount),'reason':row.reason,'created_at':row.created_at.isoformat()+'Z'}

def fingerprint(operation,body):
    data=body.model_dump(mode='json',exclude={'idempotency_key'})
    if 'amount' in data:data['amount']=str(Decimal(data['amount']).normalize())
    return hashlib.sha256((operation+json.dumps(data,sort_keys=True,separators=(',',':'))).encode()).hexdigest()

def previous(db,user,device,operation,body):
    lock_catalog(db)
    row=db.scalar(select(FinanceRequest).where(FinanceRequest.user_id==user.id,FinanceRequest.device_id==device,FinanceRequest.idempotency_key==body.idempotency_key).with_for_update())
    if row:
        if row.state=='abandoned':raise HTTPException(409,'Tentativa encerrada. Consulte os dados e revise uma nova tentativa.')
        if row.request_hash!=fingerprint(operation,body):raise HTTPException(409,'Chave usada com outra operação.')
        return {**json.loads(row.result),'replayed':True}

def complete(db,user,current,request,operation,body,result,entity,identity):
    db.add(FinanceRequest(user_id=user.id,device_id=current[0].device_id,idempotency_key=body.idempotency_key,request_hash=fingerprint(operation,body),state='completed',operation=operation,result=json.dumps(result)))
    record(db,request,user,'finance.'+operation,entity,identity);db.commit()
    return {**result,'replayed':False}

def owned_session(db,identity,user,device):
    row=db.scalar(select(CashSession).where(CashSession.id==identity).with_for_update())
    if not row or row.user_id!=user.id or row.device_id!=device:raise HTTPException(404,'Caixa não encontrado para este operador/terminal.')
    return row

def available(db,row,delta):
    after=Decimal(totals(db,row)['expected_cash'])+delta
    if after<0 or after>Decimal('999999999999.99'):raise HTTPException(409,'Movimento excede o saldo em dinheiro ou o limite do caixa.')

def ledger_sale(db,sale,user,device):
    row=current_cash(db,user,device)
    payments={m:Decimal(0) for m in ('cash','pix','debit','credit','transfer','other')}
    for payment in sale.payments:payments[payment.method]+=payment.amount
    payments['cash']-=sale.change
    available(db,row,payments['cash'])
    for method,amount in payments.items():
        if amount:db.add(CashMovement(cash_session_id=row.id,user_id=user.id,sale_id=sale.id,kind='sale',method=method,amount=amount,reason='Recebimento declarado pelo operador na venda'))

def ledger_cancel(db,sale,user,device,reason):
    original=db.scalars(select(CashMovement).where(CashMovement.sale_id==sale.id,CashMovement.kind=='sale')).all()
    if not original:return # Historical sales before cash have no invented ledger.
    row=current_cash(db,user,device)
    available(db,row,-sum((m.amount for m in original if m.method=='cash'),Decimal(0)))
    for move in original:db.add(CashMovement(cash_session_id=row.id,user_id=user.id,sale_id=sale.id,kind='sale_reversal',method=move.method,amount=-move.amount,reason=reason))

@router.get('/cash/current')
def cash_current(user:CashRead,current:Current,db:Db):
    lock_catalog(db);row=current_cash(db,user,current[0].device_id,False)
    return {'session':session_payload(db,row) if row else None}

@router.post('/cash/open',status_code=201)
def open_cash(body:Opening,user:Annotated[User,Depends(allowed('cash.open'))],current:Current,db:Db,request:Request):
    device=current[0].device_id
    cached=previous(db,user,device,'open',body)
    if cached:return cached
    if current_cash(db,user,device,False):raise HTTPException(409,'Este operador já tem caixa aberto neste terminal.')
    row=CashSession(user_id=user.id,device_id=device,opening=body.amount,note=body.reason)
    db.add(row);db.flush()
    return complete(db,user,current,request,'open',body,session_payload(db,row),'cash_sessions',row.id)

@router.post('/cash/movements',status_code=201)
def move_cash(body:Move,user:CashRead,current:Current,db:Db,request:Request):
    permission(user,'cash.'+body.kind)
    cached=previous(db,user,current[0].device_id,'movement',body)
    if cached:return cached
    row=owned_session(db,body.session_id,user,current[0].device_id)
    if row.status!='open':raise HTTPException(409,'Caixa encerrado.')
    if body.amount<=0:raise HTTPException(422,'Informe valor positivo.')
    amount=body.amount if body.kind=='deposit' else -body.amount
    available(db,row,amount)
    move=CashMovement(cash_session_id=row.id,user_id=user.id,kind=body.kind,method='cash',amount=amount,reason=body.reason)
    db.add(move);db.flush()
    return complete(db,user,current,request,'movement',body,move_payload(move),'cash_movements',move.id)

@router.post('/cash/close')
def close_cash(body:Closing,user:Annotated[User,Depends(allowed('cash.close'))],current:Current,db:Db,request:Request):
    cached=previous(db,user,current[0].device_id,'close',body)
    if cached:return cached
    row=owned_session(db,body.session_id,user,current[0].device_id)
    if row.status!='open':raise HTTPException(409,'Caixa já encerrado.')
    summary=totals(db,row)
    if summary['last_movement_id']!=body.last_movement_id:raise HTTPException(409,'Caixa movimentado. Consulte e revise novamente o fechamento.')
    # Every close requires a reason, including any cent difference.
    row.counted=body.amount;row.close_reason=body.reason;row.snapshot=json.dumps(summary);row.status='closed';row.closed_at=utcnow()
    return complete(db,user,current,request,'close',body,session_payload(db,row),'cash_sessions',row.id)

@router.get('/cash/sessions')
def sessions(user:CashRead,current:Current,db:Db,after_id:int=Query(0,ge=0),limit:int=Query(8,ge=1,le=25)):
    lock_catalog(db)
    rows=db.scalars(select(CashSession).where(CashSession.user_id==user.id,CashSession.device_id==current[0].device_id,CashSession.id>after_id).order_by(CashSession.id).limit(limit+1)).all()
    return {'items':[{k:v for k,v in session_payload(db,r).items() if k not in ('note','close_reason')} for r in rows[:limit]],'next_id':rows[limit-1].id if len(rows)>limit else None}

@router.get('/cash/sessions/{identity}')
def session_detail(identity:int,user:CashRead,current:Current,db:Db):
    lock_catalog(db);return session_payload(db,owned_session(db,identity,user,current[0].device_id))

@router.get('/cash/sessions/{identity}/movements')
def movements(identity:int,user:CashRead,current:Current,db:Db,after_id:int=Query(0,ge=0),limit:int=Query(8,ge=1,le=25)):
    owned_session(db,identity,user,current[0].device_id)
    rows=db.scalars(select(CashMovement).where(CashMovement.cash_session_id==identity,CashMovement.id>after_id).order_by(CashMovement.id).limit(limit+1)).all()
    return {'items':[move_payload(r) for r in rows[:limit]],'next_id':rows[limit-1].id if len(rows)>limit else None}

@router.get('/categories')
def categories(user:Read,db:Db,kind:Kind,after_id:int=Query(0,ge=0),limit:int=Query(8,ge=1,le=25)):
    rows=db.scalars(select(FinancialCategory).where(FinancialCategory.kind==kind,FinancialCategory.id>after_id).order_by(FinancialCategory.id).limit(limit+1)).all()
    return {'items':[{'id':r.id,'kind':r.kind,'name':r.name} for r in rows[:limit]],'next_id':rows[limit-1].id if len(rows)>limit else None}

@router.post('/categories',status_code=201)
def create_category(body:Category,user:Read,current:Current,db:Db,request:Request):
    permission(user,'cash.deposit' if body.kind=='receivable' else 'cash.withdraw')
    cached=previous(db,user,current[0].device_id,'category',body)
    if cached:return cached
    if db.scalar(select(FinancialCategory).where(FinancialCategory.kind==body.kind,FinancialCategory.name==body.name)):raise HTTPException(409,'Categoria já cadastrada.')
    row=FinancialCategory(kind=body.kind,name=body.name);db.add(row);db.flush()
    return complete(db,user,current,request,'category',body,{'id':row.id,'kind':row.kind,'name':row.name},'financial_categories',row.id)

@router.post('/accounts',status_code=201)
def create_account(body:Account,user:Read,current:Current,db:Db,request:Request):
    permission(user,'cash.deposit' if body.kind=='receivable' else 'cash.withdraw')
    cached=previous(db,user,current[0].device_id,'account',body)
    if cached:return cached
    category=db.get(FinancialCategory,body.category_id)
    if not category or category.kind!=body.kind:raise HTTPException(422,'Categoria incompatível com o tipo da conta.')
    if body.contact_id:
        contact=db.get(Contact,body.contact_id)
        if not contact or not contact.active or contact.kind!=('customer' if body.kind=='receivable' else 'supplier'):raise HTTPException(422,'Cliente/fornecedor inexistente, inativo ou incompatível.')
    row=FinancialAccount(**body.model_dump(exclude={'idempotency_key'}),user_id=user.id);db.add(row);db.flush()
    return complete(db,user,current,request,'account',body,account_payload(db,row),'financial_accounts',row.id)

@router.get('/accounts')
def accounts(user:Read,db:Db,kind:Kind,from_date:date|None=None,to_date:date|None=None,only_open:bool=False,after_id:int=Query(0,ge=0),limit:int=Query(8,ge=1,le=25)):
    if from_date and to_date and from_date>to_date:raise HTTPException(422,'Período inválido.')
    query=select(FinancialAccount).where(FinancialAccount.kind==kind,FinancialAccount.id>after_id)
    if from_date:query=query.where(FinancialAccount.due_date>=from_date)
    if to_date:query=query.where(FinancialAccount.due_date<=to_date)
    if only_open:query=query.where(FinancialAccount.paid<FinancialAccount.amount)
    rows=db.scalars(query.order_by(FinancialAccount.id).limit(limit+1)).all()
    return {'items':[account_payload(db,r) for r in rows[:limit]],'next_id':rows[limit-1].id if len(rows)>limit else None}

@router.get('/accounts/{identity}')
def account_detail(identity:int,user:Read,db:Db):
    row=db.get(FinancialAccount,identity)
    if not row:raise HTTPException(404,'Conta não encontrada.')
    return account_payload(db,row)

@router.post('/settlements',status_code=201)
def settle(body:Settlement,user:Read,current:Current,db:Db,request:Request):
    cached=previous(db,user,current[0].device_id,'settlement',body)
    if cached:return cached
    row=db.scalar(select(FinancialAccount).where(FinancialAccount.id==body.account_id).with_for_update())
    if not row:raise HTTPException(404,'Conta não encontrada.')
    permission(user,'cash.deposit' if row.kind=='receivable' else 'cash.withdraw')
    if row.version!=body.version:raise HTTPException(409,'Conta alterada. Consulte novamente antes da baixa.')
    if body.amount<=0 or body.amount>row.amount-row.paid:raise HTTPException(422,'Valor deve ser positivo e não exceder o saldo da conta.')
    session=owned_session(db,body.session_id,user,current[0].device_id)
    if session.status!='open':raise HTTPException(409,'Abra um caixa para registrar a baixa.')
    delta=body.amount if row.kind=='receivable' else -body.amount
    if body.method=='cash':available(db,session,delta)
    entry=FinancialSettlement(account_id=row.id,cash_session_id=session.id,user_id=user.id,amount=body.amount,method=body.method,reason=body.reason)
    db.add(entry);db.flush()
    db.add(CashMovement(cash_session_id=session.id,user_id=user.id,settlement_id=entry.id,kind='settlement',method=body.method,amount=delta,reason=body.reason))
    row.paid+=body.amount;row.version+=1
    return complete(db,user,current,request,'settlement',body,{'id':entry.id,'account':account_payload(db,row),'amount':money(entry.amount),'method':entry.method},'financial_settlements',entry.id)

@router.get('/accounts/{identity}/settlements')
def settlements(identity:int,user:Read,db:Db,after_id:int=Query(0,ge=0),limit:int=Query(8,ge=1,le=25)):
    if not db.get(FinancialAccount,identity):raise HTTPException(404,'Conta não encontrada.')
    rows=db.scalars(select(FinancialSettlement).where(FinancialSettlement.account_id==identity,FinancialSettlement.id>after_id).order_by(FinancialSettlement.id).limit(limit+1)).all()
    return {'items':[{'id':r.id,'amount':money(r.amount),'method':r.method,'reason':r.reason,'operator_id':r.user_id,'created_at':r.created_at.isoformat()+'Z'} for r in rows[:limit]],'next_id':rows[limit-1].id if len(rows)>limit else None}

@router.post('/requests/{key}/resolve')
def resolve(key:str,user:CashRead,current:Current,db:Db,request:Request):
    if not re.fullmatch(r'[A-Za-z0-9_-]{16,64}',key):raise HTTPException(422,'Identificador inválido.')
    lock_catalog(db)
    row=db.scalar(select(FinanceRequest).where(FinanceRequest.user_id==user.id,FinanceRequest.device_id==current[0].device_id,FinanceRequest.idempotency_key==key).with_for_update())
    if not row:
        row=FinanceRequest(user_id=user.id,device_id=current[0].device_id,idempotency_key=key,request_hash='',state='abandoned',operation='resolve');db.add(row);db.flush();record(db,request,user,'finance.resolve','finance_requests',row.id);db.commit()
    return {'state':row.state,'result':json.loads(row.result) if row.result else None,'operation':row.operation}
