# Banco de dados

MariaDB 11.8.8/InnoDB/utf8mb4, UTC, Numeric/Decimal para dinheiro, chaves
estrangeiras e índices. Cliente acessa somente API HTTPS; MariaDB sem porta pública.
Usuários SQL de aplicação (CRUD) e migração (DDL) separados; sem administração global.
Migrações Alembic incrementais até 007_reports. SQL equivalentes em database/migrations.
Não reimportar schema.sql em instalações existentes nem apagar volumes para atualizar.

Autenticação: users, roles, permissions, sessions e auditoria; produtos/categorias e
revisão de catálogo; clientes/fornecedores/vínculos; sales/sale_items/sale_payments/
sale_requests e stock_movements; inventory_requests.
0.9 acrescenta cash_sessions, cash_movements, financial_categories,
financial_accounts, financial_settlements e finance_requests.

Ledger de caixa registra movimentos assinados e pagamentos por forma, dinheiro
líquido de troco. Fechamento preserva fotografia dos totais. Não atribui vendas
históricas a caixa retroativamente. Baixas de contas parciais usam versão e não
podem exceder saldo. Chaves idempotentes por operador/terminal protegem reenvio.
Bloqueio de catálogo compartilhado serializa vendas/estoque/financeiro; conexões
MariaDB usam READ COMMITTED. Saldo/ledger/auditoria/resultado na mesma transação.

Procedimentos reais de backup/restauração em docker/scripts; atualizações de módulo
fazem backup antes da migração. CI testa MariaDB AMD64/ARM64 com concorrência e
restauração isolada. Ver [regras e atualização 0.9](releases/v0.9.0.md).

007_reports acrescenta somente índices de período, sem reescrever dados ou snapshots.
Relatórios usam agregações/janelas SQL e revisão para proteger a paginação.
