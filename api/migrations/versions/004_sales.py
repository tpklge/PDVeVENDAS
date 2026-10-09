"""Atomic sales, declared payments and stock ledger. No fiscal/payment integrations."""
from alembic import op
import sqlalchemy as sa
revision="004_sales"
down_revision="003_contacts"
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('sales',sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('user_id',sa.Integer(),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('device_id',sa.String(80),nullable=False),sa.Column('idempotency_key',sa.String(64),nullable=False),sa.Column('request_hash',sa.String(64),nullable=False),
        sa.Column('customer_id',sa.Integer(),sa.ForeignKey('contacts.id')),sa.Column('status',sa.String(16),nullable=False),
        *[sa.Column(n,sa.Numeric(14,2),nullable=False) for n in ('subtotal','discount','total','tendered','change')],
        sa.Column('created_at',sa.DateTime(),nullable=False),sa.Column('canceled_at',sa.DateTime()),
        sa.Column('canceled_by',sa.Integer(),sa.ForeignKey('users.id')),sa.Column('cancel_reason',sa.String(240)),
        sa.UniqueConstraint('user_id','device_id','idempotency_key',name='uq_sale_request'),
        sa.CheckConstraint("status IN ('completed','canceled')",name='ck_sale_status'),
        sa.CheckConstraint('subtotal >= 0 AND discount >= 0 AND total >= 0 AND change >= 0',name='ck_sale_totals'))
    op.create_table('sale_requests',sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('user_id',sa.Integer(),sa.ForeignKey('users.id'),nullable=False),sa.Column('device_id',sa.String(80),nullable=False),
        sa.Column('idempotency_key',sa.String(64),nullable=False),sa.Column('state',sa.String(16),nullable=False),
        sa.Column('sale_id',sa.Integer(),sa.ForeignKey('sales.id')),sa.Column('created_at',sa.DateTime(),nullable=False),
        sa.UniqueConstraint('user_id','device_id','idempotency_key',name='uq_sale_request_state'),
        sa.CheckConstraint("state IN ('completed','abandoned')",name='ck_sale_request_state'))
    op.create_index('ix_sales_customer_id' ,'sales',['customer_id'])
    op.create_index('ix_sales_created_at','sales',['created_at'])
    op.create_table('sale_items',sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('sale_id',sa.Integer(),sa.ForeignKey('sales.id'),nullable=False),sa.Column('product_id',sa.Integer(),sa.ForeignKey('products.id'),nullable=False),
        sa.Column('sku',sa.String(32),nullable=False),sa.Column('name',sa.String(120),nullable=False),
        sa.Column('quantity',sa.Numeric(15,3),nullable=False),sa.Column('unit_price',sa.Numeric(12,2),nullable=False),
        sa.Column('discount',sa.Numeric(14,2),nullable=False),sa.Column('subtotal',sa.Numeric(14,2),nullable=False),
        sa.CheckConstraint('quantity > 0 AND unit_price >= 0 AND discount >= 0 AND subtotal >= 0',name='ck_sale_item'))
    op.create_index('ix_sale_items_sale_id','sale_items',['sale_id'])
    op.create_table('sale_payments',sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('sale_id',sa.Integer(),sa.ForeignKey('sales.id'),nullable=False),sa.Column('method',sa.String(24),nullable=False),
        sa.Column('amount',sa.Numeric(14,2),nullable=False),sa.Column('status',sa.String(24),nullable=False),sa.CheckConstraint('amount > 0',name='ck_payment_amount'))
    op.create_index('ix_sale_payments_sale_id','sale_payments',['sale_id'])
    op.create_table('stock_movements',sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('product_id',sa.Integer(),sa.ForeignKey('products.id'),nullable=False),sa.Column('sale_id',sa.Integer(),sa.ForeignKey('sales.id')),
        sa.Column('user_id',sa.Integer(),sa.ForeignKey('users.id')),sa.Column('kind',sa.String(24),nullable=False),
        *[sa.Column(n,sa.Numeric(15,3),nullable=False) for n in ('quantity','before','after')],
        sa.Column('reason',sa.String(240),nullable=False),sa.Column('created_at',sa.DateTime(),nullable=False))
    op.create_index('ix_stock_movements_product_id','stock_movements',['product_id'])
    op.create_index('ix_stock_movements_sale_id','stock_movements',['sale_id'])
    op.get_bind().execute(sa.text("INSERT INTO stock_movements (product_id,sale_id,user_id,kind,quantity,`before`,`after`,reason,created_at) SELECT id,NULL,NULL,'opening',stock,0,stock,'Saldo anterior à etapa de vendas',updated_at FROM products WHERE stock <> 0"))

def downgrade():
    for table in ('stock_movements','sale_payments','sale_items','sale_requests','sales'):op.drop_table(table)
