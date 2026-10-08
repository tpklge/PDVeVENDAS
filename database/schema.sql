-- TAB5 ERP v0.1; gerado a partir das migrações Alembic.
-- Importar apenas em banco vazio; para atualização usar Alembic.
CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 001_foundation

CREATE TABLE app_settings (
    `key` VARCHAR(80) NOT NULL, 
    value TEXT NOT NULL, 
    PRIMARY KEY (`key`)
);

CREATE TABLE auth_audit (
    id INTEGER NOT NULL AUTO_INCREMENT, 
    subject_hash VARCHAR(64) NOT NULL, 
    success BOOL NOT NULL, 
    created_at DATETIME NOT NULL, 
    PRIMARY KEY (id)
);

CREATE INDEX ix_auth_audit_created_at ON auth_audit (created_at);

CREATE INDEX ix_auth_audit_subject_hash ON auth_audit (subject_hash);

CREATE TABLE permissions (
    id INTEGER NOT NULL AUTO_INCREMENT, 
    code VARCHAR(80) NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (code)
);

CREATE TABLE roles (
    id INTEGER NOT NULL AUTO_INCREMENT, 
    name VARCHAR(80) NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (name)
);

CREATE TABLE users (
    id INTEGER NOT NULL AUTO_INCREMENT, 
    username VARCHAR(80) NOT NULL, 
    password_hash VARCHAR(255) NOT NULL, 
    active BOOL NOT NULL, 
    must_change_password BOOL NOT NULL, 
    created_at DATETIME NOT NULL, 
    updated_at DATETIME NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (username)
);

CREATE TABLE audit_logs (
    id INTEGER NOT NULL AUTO_INCREMENT, 
    user_id INTEGER, 
    operation VARCHAR(80) NOT NULL, 
    entity VARCHAR(80) NOT NULL, 
    entity_id VARCHAR(80) NOT NULL, 
    result VARCHAR(20) NOT NULL, 
    origin VARCHAR(80) NOT NULL, 
    correlation_id VARCHAR(36) NOT NULL, 
    created_at DATETIME NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE INDEX ix_audit_logs_created_at ON audit_logs (created_at);

CREATE TABLE role_permissions (
    role_id INTEGER NOT NULL, 
    permission_id INTEGER NOT NULL, 
    PRIMARY KEY (role_id, permission_id), 
    FOREIGN KEY(permission_id) REFERENCES permissions (id), 
    FOREIGN KEY(role_id) REFERENCES roles (id)
);

CREATE TABLE sessions (
    id INTEGER NOT NULL AUTO_INCREMENT, 
    user_id INTEGER NOT NULL, 
    family VARCHAR(64) NOT NULL, 
    device_id VARCHAR(80) NOT NULL, 
    access_hash VARCHAR(64) NOT NULL, 
    refresh_hash VARCHAR(64) NOT NULL, 
    access_expires DATETIME NOT NULL, 
    refresh_expires DATETIME NOT NULL, 
    revoked BOOL NOT NULL, 
    created_at DATETIME NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id), 
    UNIQUE (access_hash), 
    UNIQUE (refresh_hash)
);

CREATE INDEX ix_sessions_family ON sessions (family);

CREATE INDEX ix_sessions_user_id ON sessions (user_id);

CREATE TABLE user_roles (
    user_id INTEGER NOT NULL, 
    role_id INTEGER NOT NULL, 
    PRIMARY KEY (user_id, role_id), 
    FOREIGN KEY(role_id) REFERENCES roles (id), 
    FOREIGN KEY(user_id) REFERENCES users (id)
);

INSERT INTO alembic_version (version_num) VALUES ('001_foundation') RETURNING alembic_version.version_num;

