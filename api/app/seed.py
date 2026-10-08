from sqlalchemy import select
from .models import Permission, Role

PERMISSIONS = {
    "products": "read create update delete", "customers": "read create update",
    "sales": "read create cancel discount", "inventory": "read adjust",
    "cash": "open close withdraw deposit", "reports": "read financial",
    "users": "read create update disable", "settings": "read update",
}
CODES = sorted(f"{module}.{action}" for module, actions in PERMISSIONS.items() for action in actions.split())
ROLE_CODES = {
    "Administrador": CODES,
    "Gerente": [code for code in CODES if code.split(".")[0] not in {"users", "settings"}],
    "Vendedor": ["products.read", "customers.read", "sales.read", "sales.create", "cash.open", "cash.close"],
    "Consulta": ["products.read", "inventory.read", "reports.read"],
}

def seed(db):
    for code in CODES:
        if not db.scalar(select(Permission).where(Permission.code == code)):
            db.add(Permission(code=code))
    db.flush()
    permissions = {p.code: p for p in db.scalars(select(Permission))}
    for name, codes in ROLE_CODES.items():
        if not db.scalar(select(Role).where(Role.name == name)):
            db.add(Role(name=name, permissions=[permissions[c] for c in codes]))
    # Existing assignments are intentionally preserved on future starts.
