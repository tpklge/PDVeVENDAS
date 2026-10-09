"""Read-only server aggregates, exact monetary strings and revision-checked pages."""
import hashlib
import json
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Annotated, Literal
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, case, cast, Numeric
from .dependencies import Db, allowed
from .models import User, Sale, SaleItem, SalePayment, Product, StockMovement
from .finance_models import CashSession, CashMovement, FinancialAccount, FinancialCategory, FinanceRequest
from .products import lock_catalog

router=APIRouter(prefix='/api/v1/reports',tags=['reports'])
Read=Annotated[User,Depends(allowed('reports.read'))]
Kind=Literal['sales','sellers','products','payments','cancellations','stock','low-stock','movements','cash','cash-sessions','receivables','payables']
ZONE=ZoneInfo('America/Cuiaba')
FINANCIAL={'sales','sellers','products','payments','cancellations','cash','cash-sessions','receivables','payables'}


def amount(value,places=2):
    value=Decimal(str(value or 0)).quantize(Decimal(1).scaleb(-places),rounding=ROUND_HALF_UP)
    return format(value,f'.{places}f')


def period(start,end):
    today=datetime.now(ZONE).date()
    start=start or end or today;end=end or start
    if start>end or (end-start).days>365 or start.year<1000 or end>=date(9999,12,31):
        raise HTTPException(422,'Informe período válido de até 366 dias em AAAA-MM-DD.')
    begin=datetime.combine(start,time.min,ZONE).astimezone(timezone.utc).replace(tzinfo=None)
    finish=datetime.combine(end+timedelta(days=1),time.min,ZONE).astimezone(timezone.utc).replace(tzinfo=None)
    return start,end,begin,finish


def revision_token(db,state,scope):
    # All commercial mutations share this lock. Financial writes do not change
    # catalog revision; their durable request IDs and cash ledger cover those too.
    facts=[state.revision,db.scalar(select(func.max(CashMovement.id))) or 0,
           db.scalar(select(func.max(FinanceRequest.id))) or 0]
    return hashlib.sha256(json.dumps([scope,facts],sort_keys=True,default=str).encode()).hexdigest()


def allocated_items(filters,db):
    # Integer cents and largest remainders: distribute at most one extra cent
    # per line, ordered by exact remainder then item ID. No line exceeds its
    # persisted subtotal; all allocated amounts sum to the sale net total.
    denominator=cast(func.sum(SaleItem.subtotal).over(partition_by=SaleItem.sale_id)*100,Numeric(30,0))
    total_cents=cast(Sale.total*100,Numeric(30,0))
    numerator=cast(SaleItem.subtotal*100,Numeric(30,0))*total_cents
    divisor=func.nullif(denominator,0)
    whole=numerator.op('DIV')(divisor) if db.bind.dialect.name!='sqlite' else func.floor(numerator/divisor)
    stage=select(SaleItem.id.label('item_id'),SaleItem.sale_id,SaleItem.product_id,SaleItem.sku,SaleItem.name,
        SaleItem.quantity,total_cents.label('total_cents'),
        cast(func.coalesce(whole,0),Numeric(30,0)).label('base'),
        cast(func.coalesce(numerator % divisor,0),Numeric(30,0)).label('remainder')).join(
        Sale,Sale.id==SaleItem.sale_id).where(*filters).subquery()
    remaining=stage.c.total_cents-func.sum(stage.c.base).over(partition_by=stage.c.sale_id)
    rank=func.row_number().over(partition_by=stage.c.sale_id,order_by=(stage.c.remainder.desc(),stage.c.item_id))
    allocated=stage.c.base+case((rank<=remaining,1),else_=0)
    return select(stage,cast(allocated/100,Numeric(24,2)).label('net')).subquery()


@router.get('/{kind}')
def report(kind:Kind,user:Read,db:Db,from_date:date|None=None,to_date:date|None=None,
           operator_id:int|None=Query(None,ge=1),product_id:int|None=Query(None,ge=1),
           only_open:bool=False,include_inactive:bool=False,
           offset:int=Query(0,ge=0,le=100000),limit:int=Query(8,ge=1,le=25),
           revision:str|None=Query(None,pattern=r'^[a-f0-9]{64}$')):
    codes={p.code for role in user.roles for p in role.permissions}
    if kind in FINANCIAL and 'reports.financial' not in codes:
        raise HTTPException(403,'Seu perfil não permite relatórios financeiros.')
    if operator_id and kind in ('stock','low-stock','receivables','payables'):
        raise HTTPException(422,'Filtro de operador não se aplica a este relatório.')
    if product_id and kind in ('sales','sellers','payments','cancellations','cash','cash-sessions','receivables','payables'):
        raise HTTPException(422,'Filtro de produto não se aplica a este relatório.')
    start,end,begin,finish=period(from_date,to_date)
    state=lock_catalog(db)
    scope={'kind':kind,'from':start.isoformat(),'to':end.isoformat(),'operator':operator_id,
           'product':product_id,'only_open':only_open,'inactive':include_inactive}
    token=revision_token(db,state,scope)
    if offset and not revision:raise HTTPException(422,'Próxima página exige a revisão da consulta.')
    if revision and revision!=token:raise HTTPException(409,'Dados alterados. Consulte a primeira página novamente.')
    sale_filters=[Sale.created_at>=begin,Sale.created_at<finish,Sale.status=='completed']
    if operator_id:sale_filters.append(Sale.user_id==operator_id)
    summary={};columns=[];query=None
    if kind in ('sales','sellers','products','payments'):
        count,gross,discount,total=db.execute(select(func.count(Sale.id),func.sum(Sale.subtotal),func.sum(Sale.discount),func.sum(Sale.total)).where(*sale_filters)).one()
        summary={'sales':count,'gross':amount(gross),'discount':amount(discount),'total':amount(total)}
        if kind=='sales':
            query=select(Sale.id,Sale.user_id,Sale.created_at,Sale.total).where(*sale_filters).order_by(Sale.id)
            columns=['Venda','Operador','Data Cuiabá','Total R$']
        elif kind=='sellers':
            query=select(Sale.user_id,User.username,func.count(Sale.id),func.sum(Sale.total)).join(User,User.id==Sale.user_id).where(*sale_filters).group_by(Sale.user_id,User.username).order_by(Sale.user_id)
            columns=['Operador','Usuário','Vendas','Total R$']
        elif kind=='products':
            items=allocated_items(sale_filters,db)
            filters=[items.c.product_id==product_id] if product_id else []
            query=select(items.c.product_id,func.min(items.c.sku),func.min(items.c.name),func.sum(items.c.quantity),func.sum(items.c.net),Product.unit).join(Product,Product.id==items.c.product_id).where(*filters).group_by(items.c.product_id,Product.unit).order_by(func.sum(items.c.quantity).desc(),items.c.product_id)
            products,total=db.execute(select(func.count(func.distinct(items.c.product_id)),func.sum(items.c.net)).where(*filters)).one()
            summary={'products':products,'total':amount(total),'ranking':'quantity','quantity_units_not_combined':True}
            columns=['Produto','SKU','Nome histórico','Quantidade','Total líquido R$','Unidade atual']
        else:
            query=select(SalePayment.method,func.count(func.distinct(SalePayment.sale_id)),func.sum(SalePayment.amount)).join(Sale,Sale.id==SalePayment.sale_id).where(*sale_filters).group_by(SalePayment.method).order_by(SalePayment.method)
            # Cash is tendered minus change, exactly once per sale, even with
            # multiple cash payment entries in one sale.
            change=db.scalar(select(func.sum(Sale.change)).where(*sale_filters)) or Decimal(0)
            query=query.subquery()
            received=cast(query.c[2]-case((query.c.method=='cash',change),else_=0),Numeric(24,2))
            query=select(query.c.method,query.c[1],received).order_by(query.c.method)
            columns=['Forma','Vendas','Recebido líquido R$']
    elif kind=='cancellations':
        filters=[Sale.status=='canceled',Sale.canceled_at>=begin,Sale.canceled_at<finish]
        if operator_id:filters.append(Sale.canceled_by==operator_id)
        count,total=db.execute(select(func.count(Sale.id),func.sum(Sale.total)).where(*filters)).one()
        summary={'cancellations':count,'total':amount(total),'external_refund_confirmed':False}
        query=select(Sale.id,Sale.canceled_by,Sale.canceled_at,Sale.total,Sale.cancel_reason).where(*filters).order_by(Sale.id)
        columns=['Venda','Cancelador','Data Cuiabá','Valor R$','Justificativa']
    elif kind in ('stock','low-stock'):
        filters=[]
        if not include_inactive:filters.append(Product.active.is_(True))
        if product_id:filters.append(Product.id==product_id)
        if kind=='low-stock':filters.append(Product.stock<=Product.stock_min)
        count=db.scalar(select(func.count(Product.id)).where(*filters))
        summary={'products':count,'current_balance':True,'quantity_units_not_combined':True}
        query=select(Product.id,Product.sku,Product.name,Product.unit,Product.stock,Product.stock_min,Product.active).where(*filters).order_by(Product.id)
        columns=['Produto','SKU','Nome','Unidade','Saldo','Mínimo','Ativo']
    elif kind=='movements':
        filters=[StockMovement.created_at>=begin,StockMovement.created_at<finish]
        if operator_id:filters.append(StockMovement.user_id==operator_id)
        if product_id:filters.append(StockMovement.product_id==product_id)
        summary={'movements':db.scalar(select(func.count(StockMovement.id)).where(*filters)),'quantity_units_not_combined':True}
        query=select(StockMovement.id,StockMovement.product_id,StockMovement.kind,StockMovement.quantity,StockMovement.before,StockMovement.after,StockMovement.created_at,StockMovement.reason).where(*filters).order_by(StockMovement.id)
        columns=['Movimento','Produto','Tipo','Variação','Antes','Após','Data Cuiabá','Justificativa']
    elif kind=='cash-sessions':
        filters=[CashSession.created_at>=begin,CashSession.created_at<finish]
        if operator_id:filters.append(CashSession.user_id==operator_id)
        raw=func.json_extract(CashSession.snapshot,'$.expected_cash')
        if db.bind.dialect.name!='sqlite':raw=func.json_unquote(raw)
        closed_expected=cast(raw,Numeric(24,2))
        count,closed,opening,expected,counted=db.execute(select(func.count(CashSession.id),
            func.sum(case((CashSession.status=='closed',1),else_=0)),func.sum(CashSession.opening),
            func.sum(closed_expected),func.sum(CashSession.counted)).where(*filters)).one()
        summary={'sessions':count,'closed':closed or 0,'opening':amount(opening),
                 'closed_expected':amount(expected),'closed_counted':amount(counted),
                 'closed_difference':amount((counted or Decimal(0))-(expected or Decimal(0)))}
        live=CashSession.opening+func.coalesce(select(func.sum(CashMovement.amount)).where(
            CashMovement.cash_session_id==CashSession.id,CashMovement.method=='cash').correlate(CashSession).scalar_subquery(),0)
        expected=cast(case((CashSession.status=='closed',closed_expected),else_=live),Numeric(24,2))
        query=select(CashSession.id,CashSession.user_id,CashSession.created_at,CashSession.status,
                     CashSession.opening,expected,CashSession.counted,CashSession.counted-expected).where(*filters).order_by(CashSession.id)
        columns=['Caixa','Operador','Abertura Cuiabá','Situação','Fundo R$','Esperado R$','Contado R$','Diferença R$']
    elif kind=='cash':
        filters=[CashMovement.created_at>=begin,CashMovement.created_at<finish]
        if operator_id:filters.append(CashMovement.user_id==operator_id)
        incoming=func.sum(case((CashMovement.amount>0,CashMovement.amount),else_=0))
        outgoing=func.sum(case((CashMovement.amount<0,-CashMovement.amount),else_=0))
        inc,out,cash=db.execute(select(incoming,outgoing,func.sum(case((CashMovement.method=='cash',CashMovement.amount),else_=0))).where(*filters)).one()
        summary={'inflows':amount(inc),'outflows':amount(out),'cash_net':amount(cash),'opening_excluded':True}
        query=select(CashMovement.method,CashMovement.kind,func.count(CashMovement.id),func.sum(CashMovement.amount)).where(*filters).group_by(CashMovement.method,CashMovement.kind).order_by(CashMovement.method,CashMovement.kind)
        columns=['Forma','Tipo','Movimentos','Valor líquido R$']
    else:
        filters=[FinancialAccount.kind==('receivable' if kind=='receivables' else 'payable'),FinancialAccount.due_date>=start,FinancialAccount.due_date<=end]
        if only_open:filters.append(FinancialAccount.paid<FinancialAccount.amount)
        count,original,paid=db.execute(select(func.count(FinancialAccount.id),func.sum(FinancialAccount.amount),func.sum(FinancialAccount.paid)).where(*filters)).one()
        summary={'accounts':count,'original':amount(original),'paid':amount(paid),'remaining':amount((original or Decimal(0))-(paid or Decimal(0))),'date_basis':'due_date'}
        query=select(FinancialAccount.id,FinancialAccount.description,FinancialCategory.name,FinancialAccount.due_date,FinancialAccount.amount,FinancialAccount.paid,FinancialAccount.amount-FinancialAccount.paid).join(FinancialCategory,FinancialCategory.id==FinancialAccount.category_id).where(*filters).order_by(FinancialAccount.id)
        columns=['Conta','Descrição','Categoria','Vencimento','Original R$','Baixado R$','Saldo R$']
    count=db.scalar(select(func.count()).select_from(query.order_by(None).subquery()))
    records=db.execute(query.offset(offset).limit(limit+1)).all()
    def cell(value):
        if isinstance(value,Decimal):return amount(value,3 if kind in ('stock','low-stock','movements','products') and value.as_tuple().exponent==-3 else 2)
        if isinstance(value,datetime):return value.replace(tzinfo=timezone.utc).astimezone(ZONE).isoformat()
        if isinstance(value,date):return value.isoformat()
        if value is None:return ''
        if isinstance(value,bool):return 'Sim' if value else 'Não'
        return str(value)
    return {'kind':kind,'timezone':'America/Cuiaba','from_date':start.isoformat(),'to_date':end.isoformat(),
            'generated_at':datetime.now(timezone.utc).isoformat(),'revision':token,'offset':offset,
            'next_offset':offset+limit if len(records)>limit else None,'rows_total':count,
            'summary':summary,'columns':columns,'rows':[[cell(v) for v in row] for row in records[:limit]]}
