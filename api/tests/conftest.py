import os
os.environ["DATABASE_URL"] = "sqlite://"
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from alembic import command
from alembic.config import Config
from app.db import get_db
from app.main import app
from app.models import User, Role
from app.security import hasher
from app.seed import seed

PASSWORD = "testing-only-password-0123456789"

@pytest.fixture()
def environment(tmp_path, monkeypatch):
    path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", "sqlite:///" + str(path))
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "migrations"))
    command.upgrade(config, "head")
    command.upgrade(config, "head")
    engine = create_engine("sqlite:///" + str(path), connect_args={"check_same_thread": False})
    @event.listens_for(engine, "connect")
    def foreign_keys(connection, record):
        connection.execute("PRAGMA foreign_keys=ON")
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory.begin() as db:
        seed(db)
        seed(db)
        admin = db.query(Role).filter_by(name="Administrador").one()
        viewer = db.query(Role).filter_by(name="Consulta").one()
        db.add(User(username="admin", password_hash=hasher.hash(PASSWORD), roles=[admin]))
        db.add(User(username="viewer", password_hash=hasher.hash(PASSWORD), roles=[viewer], must_change_password=False))
    def dependency():
        with factory() as db:
            yield db
    app.dependency_overrides[get_db] = dependency
    with TestClient(app) as client:
        yield client, factory
    app.dependency_overrides.clear()
    engine.dispose()


def legacy_product(db, **values):
    """Insert using the historical schema, not columns introduced by later ORM models."""
    from sqlalchemy import MetaData, Table, insert
    from app.models import utcnow
    defaults = dict(description='', unit='UN', cost_price=0, stock=0, stock_min=0,
                    active=True, version=1, created_at=utcnow(), updated_at=utcnow())
    table = Table('products', MetaData(), autoload_with=db.connection())
    result = db.execute(insert(table).values(**{**defaults, **values}))
    return result.inserted_primary_key[0]
