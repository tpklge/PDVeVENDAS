# API TAB5 ERP 0.5.0

FastAPI, JSON UTF-8, /api/v1. Autenticação/RBAC existentes preservados.
Capabilities auth, rbac, products, catalog_snapshot. Schema esperado 002_products.
A API não implementa PDV nesta etapa. Autenticação opaca, refresh rotativo,
revogação e senha ERP de pelo menos 8 caracteres continuam em vigor.

Ver [release de produtos](releases/v0.5.0.md) para migração, endpoints, campos,
permissões, cache e testes. Documentação OpenAPI é gerada pela aplicação.

## Clientes e fornecedores — 0.6.0

GET/POST `/api/v1/customers` e `/api/v1/suppliers`; GET/PUT/DELETE por ID.
POST `/{módulo}/search` pesquisa nome/documento no corpo, com paginação por ID.
GET `/{módulo}/{id}/history` mostra eventos de alterações; compras dependem do PDV.
GET/POST `/suppliers/{id}/products` e DELETE `/suppliers/{id}/products/{product_id}`.
Documento opcional, CPF/CNPJ numérico/alfanumérico; permissões `.documents`
separadas de leitura/edição. Dados pessoais ficam somente na RAM do Tab5;
listagens mínimas e auditoria sem os valores dos campos pessoais.
Ver [migração, permissões e teste físico](releases/v0.6.0.md).
