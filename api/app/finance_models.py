"""Cash and accounts ledger; monetary values are exact decimal amounts."""
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import ForeignKey, String, Numeric, Date, DateTime, Text, CheckConstraint, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .models import Base, utcnow

class CashSession(Base):
    __tablename__='cash_sessions'
    __table_args__=(CheckConstraint("status IN ('open','closed')",name='ck_cash_status'), CheckConstraint('opening >= 0 AND counted >= 0',name='ck_cash_amounts'))
    id: Mapped[int]=mapped_column(primary_key=True)
    user_id: Mapped[int]=mapped_column(ForeignKey('users.id'),index=True)
    device_id: Mapped[str]=mapped_column(String(80))
    status: Mapped[str]=mapped_column(String(16),default='open')
    opening: Mapped[Decimal]=mapped_column(Numeric(14,2))
    counted: Mapped[Decimal|None]=mapped_column(Numeric(14,2))
    note: Mapped[str]=mapped_column(String(240))
    close_reason: Mapped[str|None]=mapped_column(String(240))
    snapshot: Mapped[str|None]=mapped_column(Text)
    created_at: Mapped[datetime]=mapped_column(DateTime,default=utcnow)
    closed_at: Mapped[datetime|None]=mapped_column(DateTime)

class FinancialCategory(Base):
    __tablename__='financial_categories'
    __table_args__=(UniqueConstraint('kind','name',name='uq_financial_category'),CheckConstraint("kind IN ('receivable','payable')",name='ck_financial_category_kind'))
    id: Mapped[int]=mapped_column(primary_key=True)
    kind: Mapped[str]=mapped_column(String(16))
    name: Mapped[str]=mapped_column(String(80))

class FinancialAccount(Base):
    __tablename__='financial_accounts'
    __table_args__=(CheckConstraint("kind IN ('receivable','payable')",name='ck_financial_account_kind'),CheckConstraint('amount > 0 AND paid >= 0 AND paid <= amount',name='ck_financial_account_amount'))
    id: Mapped[int]=mapped_column(primary_key=True)
    kind: Mapped[str]=mapped_column(String(16),index=True)
    category_id: Mapped[int]=mapped_column(ForeignKey('financial_categories.id'))
    contact_id: Mapped[int|None]=mapped_column(ForeignKey('contacts.id'))
    description: Mapped[str]=mapped_column(String(240))
    due_date: Mapped[date]=mapped_column(Date,index=True)
    amount: Mapped[Decimal]=mapped_column(Numeric(14,2))
    paid: Mapped[Decimal]=mapped_column(Numeric(14,2),default=0)
    version: Mapped[int]=mapped_column(default=1)
    user_id: Mapped[int]=mapped_column(ForeignKey('users.id'))
    created_at: Mapped[datetime]=mapped_column(DateTime,default=utcnow)

class FinancialSettlement(Base):
    __tablename__='financial_settlements'
    __table_args__=(CheckConstraint('amount > 0',name='ck_financial_settlement_amount'),)
    id: Mapped[int]=mapped_column(primary_key=True)
    account_id: Mapped[int]=mapped_column(ForeignKey('financial_accounts.id'),index=True)
    cash_session_id: Mapped[int]=mapped_column(ForeignKey('cash_sessions.id'))
    user_id: Mapped[int]=mapped_column(ForeignKey('users.id'))
    amount: Mapped[Decimal]=mapped_column(Numeric(14,2))
    method: Mapped[str]=mapped_column(String(24))
    reason: Mapped[str]=mapped_column(String(240))
    created_at: Mapped[datetime]=mapped_column(DateTime,default=utcnow)

class CashMovement(Base):
    __tablename__='cash_movements'
    id: Mapped[int]=mapped_column(primary_key=True)
    cash_session_id: Mapped[int]=mapped_column(ForeignKey('cash_sessions.id'),index=True)
    user_id: Mapped[int]=mapped_column(ForeignKey('users.id'))
    sale_id: Mapped[int|None]=mapped_column(ForeignKey('sales.id'),index=True)
    settlement_id: Mapped[int|None]=mapped_column(ForeignKey('financial_settlements.id'))
    kind: Mapped[str]=mapped_column(String(24))
    method: Mapped[str]=mapped_column(String(24))
    amount: Mapped[Decimal]=mapped_column(Numeric(14,2))
    reason: Mapped[str]=mapped_column(String(240))
    created_at: Mapped[datetime]=mapped_column(DateTime,default=utcnow)

class FinanceRequest(Base):
    __tablename__='finance_requests'
    __table_args__=(UniqueConstraint('user_id','device_id','idempotency_key',name='uq_finance_request'),CheckConstraint("state IN ('completed','abandoned')",name='ck_finance_request_state'))
    id: Mapped[int]=mapped_column(primary_key=True)
    user_id: Mapped[int]=mapped_column(ForeignKey('users.id'))
    device_id: Mapped[str]=mapped_column(String(80))
    idempotency_key: Mapped[str]=mapped_column(String(64))
    request_hash: Mapped[str]=mapped_column(String(64))
    state: Mapped[str]=mapped_column(String(16))
    operation: Mapped[str]=mapped_column(String(32))
    result: Mapped[str|None]=mapped_column(Text)
    created_at: Mapped[datetime]=mapped_column(DateTime,default=utcnow)
