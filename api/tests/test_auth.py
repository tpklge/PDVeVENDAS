from datetime import timedelta
from sqlalchemy import select, update
from app.models import AuthAudit, Permission, Role, Session, User, utcnow
from app.security import digest
from conftest import PASSWORD


def login(client, username="admin", password=PASSWORD):
    return client.post("/api/v1/auth/login", json={"username": username, "password": password, "device_id": "tab5-test"})


def headers(token):
    return {"Authorization": "Bearer " + token}


def test_health_and_migrations(environment):
    client, factory = environment
    assert client.get("/health/live").status_code == 200
    assert client.get("/health/ready").status_code == 200
    assert client.get("/api/v1/system/status").json()["commercial_operations"] is False
    with factory() as db:
        assert len(list(db.scalars(select(Role)))) == 4
        assert len(list(db.scalars(select(Permission)))) == 25


def test_mandatory_password_change_and_revocation(environment):
    client, factory = environment
    result = login(client).json()
    auth = headers(result["access_token"])
    assert result["must_change_password"] is True
    assert client.get("/api/v1/users", headers=auth).status_code == 403
    assert client.post("/api/v1/auth/change-password", headers=auth,
        json={"current_password": PASSWORD, "new_password": "new-testing-password-0123456789"}).status_code == 204
    assert client.get("/api/v1/auth/me", headers=auth).status_code == 401
    assert login(client).status_code == 401
    new = login(client, password="new-testing-password-0123456789").json()
    assert client.get("/api/v1/users", headers=headers(new["access_token"])).status_code == 200
    with factory() as db:
        assert db.query(User).filter_by(username="admin").one().password_hash.startswith("$argon2id$")


def test_refresh_rotation_and_replay_revokes_family(environment):
    client, _ = environment
    original = login(client).json()
    body = {"refresh_token": original["refresh_token"], "device_id": "tab5-test"}
    rotated = client.post("/api/v1/auth/refresh", json=body).json()
    assert rotated["access_token"] != original["access_token"]
    assert client.get("/api/v1/auth/me", headers=headers(original["access_token"])).status_code == 401
    assert client.get("/api/v1/auth/me", headers=headers(rotated["access_token"])).status_code == 200
    assert client.post("/api/v1/auth/refresh", json=body).status_code == 401
    assert client.get("/api/v1/auth/me", headers=headers(rotated["access_token"])).status_code == 401


def test_wrong_device_and_logout(environment):
    client, _ = environment
    tokens = login(client).json()
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"], "device_id": "other"}).status_code == 401
    auth = headers(tokens["access_token"])
    assert client.post("/api/v1/auth/logout", headers=auth).status_code == 204
    assert client.get("/api/v1/auth/me", headers=auth).status_code == 401


def test_inactive_user_and_expired_access(environment):
    client, factory = environment
    token = login(client).json()["access_token"]
    with factory.begin() as db:
        db.execute(update(Session).where(Session.access_hash == digest(token)).values(access_expires=utcnow()-timedelta(seconds=1)))
    assert client.get("/api/v1/auth/me", headers=headers(token)).status_code == 401
    with factory.begin() as db:
        db.query(User).filter_by(username="admin").one().active = False
    assert login(client).status_code == 401


def test_rbac_viewer_and_no_credentials(environment):
    client, _ = environment
    token = login(client, username="viewer").json()["access_token"]
    assert client.get("/api/v1/users", headers=headers(token)).status_code == 403
    me = client.get("/api/v1/auth/me", headers=headers(token))
    assert "password_hash" not in me.json()
    assert PASSWORD not in me.text
    assert me.json()["permissions"] == ["inventory.read", "products.read", "reports.read"]


def test_login_limit_and_generic_errors(environment):
    client, _ = environment
    for _ in range(5):
        assert login(client, password="wrong-password").status_code == 401
    limited = login(client)
    assert limited.status_code == 429
    assert limited.json()["error"]["correlation_id"] == limited.headers["X-Correlation-ID"]
    assert "wrong-password" not in limited.text


def test_validation_does_not_echo_password(environment):
    client, _ = environment
    result = client.post("/api/v1/auth/login", json={"username": "admin", "password": "SENSITIVE"*100, "device_id": "test"})
    assert result.status_code == 422
    assert "SENSITIVE" not in result.text
    assert client.get("/api/v1/users").status_code == 401
