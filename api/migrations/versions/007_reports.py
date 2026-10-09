"""Add period indexes without changing financial data or historical snapshots."""
from alembic import op
revision='007_reports'
down_revision='006_cash'
branch_labels=None
depends_on=None
INDEXES=(
    ('ix_reports_sales_period','sales',['status','created_at']),
    ('ix_reports_sales_cancel_period','sales',['canceled_at']),
    ('ix_reports_stock_period','stock_movements',['created_at','product_id']),
    ('ix_reports_cash_period','cash_movements',['created_at','user_id']),
    ('ix_reports_cash_session_period','cash_sessions',['created_at']),
    ('ix_reports_account_due','financial_accounts',['kind','due_date']),
)
def upgrade():
    for name,table,columns in INDEXES:op.create_index(name,table,columns)
def downgrade():
    for name,table,_ in reversed(INDEXES):op.drop_index(name,table_name=table)
