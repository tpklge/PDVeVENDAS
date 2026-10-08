"""Product catalog; incremental, preserves authentication and existing data."""
from alembic import op
import sqlalchemy as sa

revision = "002_products"
down_revision = "001_foundation"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("categories", sa.Column("id", sa.Integer(), primary_key=True),
                    sa.Column("name", sa.String(80), nullable=False, unique=True))
    state = op.create_table("catalog_state", sa.Column("id", sa.Integer(), primary_key=True),
                           sa.Column("revision", sa.Integer(), nullable=False))
    op.bulk_insert(state, [{"id": 1, "revision": 1}])
    op.create_table("products",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sku", sa.String(32), nullable=False, unique=True),
        sa.Column("barcode", sa.String(14), unique=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("categories.id")),
        sa.Column("unit", sa.String(8), nullable=False),
        sa.Column("cost_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("sale_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("stock", sa.Numeric(15, 3), nullable=False),
        sa.Column("stock_min", sa.Numeric(15, 3), nullable=False),
        sa.Column("stock_max", sa.Numeric(15, 3)),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("ncm", sa.String(8)), sa.Column("cest", sa.String(7)), sa.Column("origin", sa.Integer()),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("cost_price >= 0 AND sale_price >= 0", name="ck_product_prices"),
        sa.CheckConstraint("stock >= 0 AND stock_min >= 0", name="ck_product_stock"))
    op.create_index("ix_products_name", "products", ["name"])
    op.create_index("ix_products_category_id", "products", ["category_id"])


def downgrade():
    op.drop_table("products")
    op.drop_table("catalog_state")
    op.drop_table("categories")
