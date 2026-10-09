from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from .config import database_url

url = database_url()
# Authentication reads precede inventory locks. Under MariaDB snapshot isolation,
# REPEATABLE READ can reject a waiting lock after another sale commits (1020).
# READ COMMITTED gives each locking statement the latest committed view; explicit
# catalog/product locks still serialize stock changes and idempotency decisions.
options = {"isolation_level": "READ COMMITTED"} if make_url(url).get_backend_name() in {"mysql", "mariadb"} else {}
engine = create_engine(url, pool_pre_ping=True, pool_recycle=1800, **options)
SessionFactory = sessionmaker(bind=engine, expire_on_commit=False)

def get_db():
    with SessionFactory() as db:
        yield db
