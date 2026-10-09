-- Referência MariaDB; implantar com Alembic, sem importar este arquivo no banco existente.
-- UUID novo por implantação/restauração; nenhum dado comercial é recalculado.
ALTER TABLE catalog_state ADD COLUMN epoch VARCHAR(36) NOT NULL DEFAULT '';
UPDATE catalog_state SET epoch = UUID();
ALTER TABLE products ADD COLUMN sync_revision INTEGER NOT NULL DEFAULT 1;
UPDATE products SET sync_revision = (SELECT revision FROM catalog_state WHERE id = 1);
CREATE INDEX ix_products_sync_revision ON products (sync_revision);
