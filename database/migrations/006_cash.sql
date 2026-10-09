-- Running upgrade 005_inventory -> 006_cash

CREATE TABLE cash_sessions (
    id INTEGER NOT NULL AUTO_INCREMENT,
    user_id INTEGER NOT NULL,
    device_id VARCHAR(80) NOT NULL,
    status VARCHAR(16) NOT NULL,
    opening NUMERIC(14, 2) NOT NULL,
    counted NUMERIC(14, 2),
    note VARCHAR(240) NOT NULL,
    close_reason VARCHAR(240),
    snapshot TEXT,
    created_at DATETIME NOT NULL,
    closed_at DATETIME,
    PRIMARY KEY (id),
    CONSTRAINT ck_cash_status CHECK (status IN ('open','closed')),
    CONSTRAINT ck_cash_amounts CHECK (opening >= 0 AND counted >= 0),
    FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE INDEX ix_cash_sessions_user_id ON cash_sessions (user_id);

CREATE TABLE financial_categories (
    id INTEGER NOT NULL AUTO_INCREMENT,
    kind VARCHAR(16) NOT NULL,
    name VARCHAR(80) NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_financial_category UNIQUE (kind, name),
    CONSTRAINT ck_financial_category_kind CHECK (kind IN ('receivable','payable'))
);

CREATE TABLE financial_accounts (
    id INTEGER NOT NULL AUTO_INCREMENT,
    kind VARCHAR(16) NOT NULL,
    category_id INTEGER NOT NULL,
    contact_id INTEGER,
    description VARCHAR(240) NOT NULL,
    due_date DATE NOT NULL,
    amount NUMERIC(14, 2) NOT NULL,
    paid NUMERIC(14, 2) NOT NULL,
    version INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    created_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT ck_financial_account_kind CHECK (kind IN ('receivable','payable')),
    CONSTRAINT ck_financial_account_amount CHECK (amount > 0 AND paid >= 0 AND paid <= amount),
    FOREIGN KEY(category_id) REFERENCES financial_categories (id),
    FOREIGN KEY(contact_id) REFERENCES contacts (id),
    FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE INDEX ix_financial_accounts_kind ON financial_accounts (kind);

CREATE INDEX ix_financial_accounts_due_date ON financial_accounts (due_date);

CREATE TABLE financial_settlements (
    id INTEGER NOT NULL AUTO_INCREMENT,
    account_id INTEGER NOT NULL,
    cash_session_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    amount NUMERIC(14, 2) NOT NULL,
    method VARCHAR(24) NOT NULL,
    reason VARCHAR(240) NOT NULL,
    created_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT ck_financial_settlement_amount CHECK (amount > 0),
    FOREIGN KEY(account_id) REFERENCES financial_accounts (id),
    FOREIGN KEY(cash_session_id) REFERENCES cash_sessions (id),
    FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE INDEX ix_financial_settlements_account_id ON financial_settlements (account_id);

CREATE TABLE cash_movements (
    id INTEGER NOT NULL AUTO_INCREMENT,
    cash_session_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    sale_id INTEGER,
    settlement_id INTEGER,
    kind VARCHAR(24) NOT NULL,
    method VARCHAR(24) NOT NULL,
    amount NUMERIC(14, 2) NOT NULL,
    reason VARCHAR(240) NOT NULL,
    created_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(cash_session_id) REFERENCES cash_sessions (id),
    FOREIGN KEY(user_id) REFERENCES users (id),
    FOREIGN KEY(sale_id) REFERENCES sales (id),
    FOREIGN KEY(settlement_id) REFERENCES financial_settlements (id)
);

CREATE INDEX ix_cash_movements_cash_session_id ON cash_movements (cash_session_id);

CREATE INDEX ix_cash_movements_sale_id ON cash_movements (sale_id);

CREATE TABLE finance_requests (
    id INTEGER NOT NULL AUTO_INCREMENT,
    user_id INTEGER NOT NULL,
    device_id VARCHAR(80) NOT NULL,
    idempotency_key VARCHAR(64) NOT NULL,
    request_hash VARCHAR(64) NOT NULL,
    state VARCHAR(16) NOT NULL,
    operation VARCHAR(32) NOT NULL,
    result TEXT,
    created_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_finance_request UNIQUE (user_id, device_id, idempotency_key),
    CONSTRAINT ck_finance_request_state CHECK (state IN ('completed','abandoned')),
    FOREIGN KEY(user_id) REFERENCES users (id)
);

UPDATE alembic_version SET version_num='006_cash' WHERE alembic_version.version_num = '005_inventory';
