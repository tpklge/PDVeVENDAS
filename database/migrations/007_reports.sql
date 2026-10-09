-- Running upgrade 006_cash -> 007_reports

CREATE INDEX ix_reports_sales_period ON sales (status, created_at);

CREATE INDEX ix_reports_sales_cancel_period ON sales (canceled_at);

CREATE INDEX ix_reports_stock_period ON stock_movements (created_at, product_id);

CREATE INDEX ix_reports_cash_period ON cash_movements (created_at, user_id);

CREATE INDEX ix_reports_cash_session_period ON cash_sessions (created_at);

CREATE INDEX ix_reports_account_due ON financial_accounts (kind, due_date);

UPDATE alembic_version SET version_num='007_reports' WHERE alembic_version.version_num = '006_cash';
