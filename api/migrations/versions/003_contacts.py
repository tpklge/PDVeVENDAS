"""Customers and suppliers; additive migration and explicit privileged documents."""
from alembic import op
import sqlalchemy as sa
revision = "003_contacts"
down_revision = "002_products"
branch_labels = None
depends_on = None
NEW_CODES = ("customers.delete", "customers.documents", "suppliers.read", "suppliers.create", "suppliers.update", "suppliers.delete", "suppliers.documents")

def upgrade():
    op.create_table("contacts", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("kind", sa.String(16), nullable=False), sa.Column("name", sa.String(120), nullable=False),
        sa.Column("person_type", sa.String(2), nullable=False), sa.Column("document", sa.String(14)),
        *[sa.Column(name, sa.String(length), nullable=False) for name, length in (
            ("trade_name",120),("phone",32),("email",160),("address",200),("city",80),("state",2),("postal_code",8),("contact_name",120),("notes",500))],
        sa.Column("active", sa.Boolean(), nullable=False), sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("kind", "document", name="uq_contact_document"),
        sa.CheckConstraint("kind IN ('customer','supplier')", name="ck_contact_kind"),
        sa.CheckConstraint("person_type IN ('PF','PJ')", name="ck_contact_person"))
    op.create_index("ix_contacts_kind", "contacts", ["kind"])
    op.create_index("ix_contacts_name", "contacts", ["name"])
    op.create_table("supplier_products", sa.Column("supplier_id", sa.Integer(), sa.ForeignKey("contacts.id"), primary_key=True),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), primary_key=True))
    db = op.get_bind()
    for code in NEW_CODES:
        db.execute(sa.text("INSERT INTO permissions (code) VALUES (:code)"), {"code":code})
        for role in ("Administrador", "Gerente"):
            db.execute(sa.text("INSERT INTO role_permissions (role_id, permission_id) SELECT r.id, p.id FROM roles r JOIN permissions p ON p.code=:code WHERE r.name=:role"), {"code":code,"role":role})

def downgrade():
    op.drop_table("supplier_products")
    op.drop_index("ix_contacts_name", table_name="contacts")
    op.drop_index("ix_contacts_kind", table_name="contacts")
    op.drop_table("contacts")
    db = op.get_bind()
    for code in NEW_CODES:
        db.execute(sa.text("DELETE FROM role_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE code=:code)"), {"code":code})
        db.execute(sa.text("DELETE FROM permissions WHERE code=:code"), {"code":code})
