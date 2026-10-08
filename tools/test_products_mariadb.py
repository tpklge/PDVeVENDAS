"""HTTP integration against the isolated MariaDB Docker stack in CI only."""
import json
import os
from pathlib import Path
import urllib.request
import urllib.error

if os.environ.get("CI") != "true":
    raise SystemExit("Teste destinado apenas ao ambiente isolado de CI.")


def call(method, path, body=None, token=None, expected=200):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request("http://api:8000" + path,
        data=json.dumps(body).encode() if body is not None else None, headers=headers, method=method)
    try:
        response = urllib.request.urlopen(request, timeout=20)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        assert response.status == expected, f"{method} {path}: HTTP {response.status}, esperado {expected}"
        content = response.read()
        return json.loads(content) if content else None


password = Path("/run/test/admin_password").read_text().strip()
session = call("POST", "/api/v1/auth/login", {"username": "admin", "password": password, "device_id": "ci-products"})
call("POST", "/api/v1/auth/change-password", {"current_password": password,
    "new_password": "ci-isolated-only-password"}, session["access_token"], 204)
session = call("POST", "/api/v1/auth/login", {"username": "admin", "password": "ci-isolated-only-password", "device_id": "ci-products"})
token = session["access_token"]
body = {"sku": "CI-PRODUCT", "name": "Café São João", "category": "CI Mercearia", "sale_price": "123.45", "stock": "2.500", "stock_min": "3"}
product = call("POST", "/api/v1/products", body, token, 201)
assert product["sale_price"] == "123.45" and product["stock"] == "2.500" and product["stock_low"]
call("POST", "/api/v1/products", body, token, 409)
snapshot = call("GET", "/api/v1/products?limit=2", token=token)
updated = call("PUT", f"/api/v1/products/{product['id']}", {**body, "version": 1, "sale_price": "145.90"}, token)
assert updated["version"] == 2 and updated["sale_price"] == "145.90"
call("PUT", f"/api/v1/products/{product['id']}", {**body, "version": 1}, token, 409)
call("GET", f"/api/v1/products?revision={snapshot['revision']}", token=token, expected=409)
call("DELETE", f"/api/v1/products/{product['id']}?version=2", token=token, expected=204)
assert not call("GET", "/api/v1/products", token=token)["items"]
assert call("GET", "/api/v1/products?include_inactive=true", token=token)["items"][0]["active"] is False
print("PASS: MariaDB real — preços decimais, CRUD, duplicidade, revisão, conflito e inativação.")
