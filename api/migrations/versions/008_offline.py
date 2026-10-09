"""Track committed product revisions, preserving all existing business data."""
from uuid import uuid4
from alembic import op
import sqlalchemy as sa

revision = '008_offline'
down_revision = '007_reports'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('catalog_state', sa.Column('epoch', sa.String(36), nullable=False,
                                          server_default=''))
    op.execute(sa.text('UPDATE catalog_state SET epoch = :epoch').bindparams(epoch=str(uuid4())))
    op.add_column('products', sa.Column('sync_revision', sa.Integer(), nullable=False,
                                      server_default='1'))
    op.execute('UPDATE products SET sync_revision = (SELECT revision FROM catalog_state WHERE id = 1)')
    op.create_index('ix_products_sync_revision', 'products', ['sync_revision'])


def downgrade():
    op.drop_index('ix_products_sync_revision', table_name='products')
    op.drop_column('products', 'sync_revision')
    op.drop_column('catalog_state', 'epoch')
