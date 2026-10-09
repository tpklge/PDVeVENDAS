"""Durable results for inventory retries; preserve all existing stock movements."""
from alembic import op
import sqlalchemy as sa
revision = '005_inventory'
down_revision = '004_sales'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('inventory_requests',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('device_id', sa.String(80), nullable=False),
        sa.Column('idempotency_key', sa.String(64), nullable=False),
        sa.Column('request_hash', sa.String(64), nullable=False),
        sa.Column('state', sa.String(16), nullable=False),
        sa.Column('movement_id', sa.Integer(), sa.ForeignKey('stock_movements.id')),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('user_id', 'device_id', 'idempotency_key', name='uq_inventory_request'),
        sa.CheckConstraint("state IN ('completed','abandoned')", name='ck_inventory_request_state'))


def downgrade():
    op.drop_table('inventory_requests')
