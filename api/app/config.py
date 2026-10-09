import os
from pathlib import Path
from sqlalchemy import URL

VERSION = "0.10.0"
SCHEMA_REVISION = "007_reports"

def database_url():
    if os.getenv("DATABASE_URL"):
        return os.environ["DATABASE_URL"]
    password = Path(os.environ.get("DB_PASSWORD_FILE", "/run/secrets/db_app_password")).read_text().strip()
    return URL.create("mariadb+pymysql", username=os.environ.get("DB_USER", "tab5_app"),
                      password=password, host=os.environ.get("DB_HOST", "mariadb"),
                      database="tab5_erp", query={"charset": "utf8mb4"})
