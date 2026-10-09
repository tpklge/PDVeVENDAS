# API TAB5 ERP 0.9.0

FastAPI, JSON UTF-8, /api/v1, schema esperado 006_cash. HTTPS via Traefik.
Autenticação opaca, refresh rotativo, revogação, RBAC e senha ERP mínimo 8 caracteres.
Capabilities auth, rbac, products, catalog_snapshot, customers, suppliers, sales,
declared_payments, inventory, cash, finance. OpenAPI gerado pela aplicação.

Produtos/categorias: [contratos 0.5](releases/v0.5.0.md).
Clientes/fornecedores, documentos e histórico: [contratos 0.6](releases/v0.6.0.md).
Vendas/PDV, pagamentos declarados, idempotência/cancelamento: [0.7](releases/v0.7.0.md).
Saldo, entradas/saídas/ajustes e recuperação: [0.8](releases/v0.8.0.md).
Caixa, categorias financeiras, contas e baixas: [0.9](releases/v0.9.0.md).

API 0.9 exige caixa aberto no operador/terminal para concluir novas vendas.
Troco só em dinheiro, pagamentos separados por forma. Contas financeiras manuais
não são recebíveis gerados automaticamente de pagamentos já declarados de vendas.
Operações financeiras possuem chaves idempotentes e resolução contra envio tardio.
Listagens de caixa/contas usam limit máximo 25, after_id e next_id; Tab5 usa 8.
Consultar a release correspondente para permissões, campos e migração.
