from sqlalchemy import select
from app.models import User, Product, AuditLog
from conftest import PASSWORD


def credentials(environment, username="admin"):
    client, factory = environment
    with factory.begin() as db:
        db.scalar(select(User).where(User.username == username)).must_change_password = False
    token = client.post("/api/v1/auth/login", json={"username": username, "password": PASSWORD, "device_id": "products-test"}).json()["access_token"]
    return {"Authorization": "Bearer " + token}


def product(**changes):
    return {"sku": "cafe-01", "name": "Café São João", "category": "Bebidas", "sale_price": "12.30",
            "cost_price": "7.11", "stock": "2.500", "stock_min": "3", **changes}


def test_crud_decimal_filters_and_soft_delete(environment):
    client, factory = environment
    auth = credentials(environment)
    response = client.post("/api/v1/products", headers=auth, json=product())
    assert response.status_code == 201, response.text
    row = response.json()
    assert row["sku"] == "CAFE-01" and row["sale_price"] == "12.30" and row["stock_low"] is True
    assert client.get("/api/v1/products?q=Café&category=Bebidas", headers=auth).json()["items"][0]["id"] == row["id"]
    assert client.get("/api/v1/products?q=%", headers=auth).json()["items"] == []
    edit = client.put(f"/api/v1/products/{row['id']}", headers=auth,
                      json=product(version=row["version"], sale_price="15.90"))
    assert edit.status_code == 200, edit.text
    assert edit.json()["version"] == 2 and edit.json()["sale_price"] == "15.90"
    assert client.put(f"/api/v1/products/{row['id']}", headers=auth, json=product(version=1)).status_code == 409
    assert client.delete(f"/api/v1/products/{row['id']}?version=2", headers=auth).status_code == 204
    assert client.get("/api/v1/products", headers=auth).json()["items"] == []
    assert client.get("/api/v1/products?include_inactive=true", headers=auth).json()["items"][0]["active"] is False
    with factory() as db:
        assert db.get(Product, row["id"]) is not None
        assert len(db.scalars(select(AuditLog).where(AuditLog.entity == "products")).all()) == 3


def test_validation_duplicates_and_categories(environment):
    client, _ = environment
    auth = credentials(environment)
    for changes in ({"sale_price": "-1"}, {"sale_price": "1.001"}, {"name": " "},
                    {"barcode": "7891234567890"}, {"stock_min": "10", "stock_max": "2"}):
        assert client.post("/api/v1/products", headers=auth, json=product(**changes)).status_code == 422
    assert client.post("/api/v1/products", headers=auth, json=product(barcode="7894900011517")).status_code == 201
    assert client.post("/api/v1/products", headers=auth, json=product()).status_code == 409
    assert client.post("/api/v1/products", headers=auth, json=product(sku="other", barcode="7894900011517")).status_code == 409
    categories = client.get("/api/v1/categories", headers=auth).json()["items"]
    assert categories[0]["name"] == "Bebidas"
    assert client.put(f"/api/v1/categories/{categories[0]['id']}", headers=auth, json={"name": "Mercearia"}).status_code == 200
    assert client.get("/api/v1/products", headers=auth).json()["items"][0]["category"] == "Mercearia"


def test_snapshot_revision_rbac_and_pagination(environment):
    client, _ = environment
    admin = credentials(environment)
    viewer = credentials(environment, "viewer")
    assert client.get("/api/v1/products").status_code == 401
    assert client.post("/api/v1/products", headers=viewer, json=product()).status_code == 403
    for index in range(3):
        assert client.post("/api/v1/products", headers=admin, json=product(sku=f"SKU{index}")).status_code == 201
    page = client.get("/api/v1/products?limit=2", headers=viewer).json()
    assert len(page["items"]) == 2 and page["next_id"]
    next_page = client.get(f"/api/v1/products?after_id={page['next_id']}&limit=2&revision={page['revision']}", headers=viewer).json()
    assert len(next_page["items"]) == 1 and next_page["next_id"] is None
    assert client.post("/api/v1/products", headers=admin, json=product(sku="new")).status_code == 201
    assert client.get(f"/api/v1/products?revision={page['revision']}", headers=viewer).status_code == 409
