from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .config import database_url

engine = create_engine(database_url(), pool_pre_ping=True, pool_recycle=1800)
SessionFactory = sessionmaker(bind=engine, expire_on_commit=False)

def get_db():
    with SessionFactory() as db:
        yield db
