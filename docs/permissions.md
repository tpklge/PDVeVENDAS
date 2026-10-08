# Permissões

A plataforma v0.1.0 possui somente diagnóstico/teste de entrada/armazenamento.
Não possui acesso a dados comerciais nem autenticação.

Papéis futuros: Administrador, Gerente, Vendedor, Consulta. RBAC servidor em tabelas
users/roles/permissions/user_roles/role_permissions; validação em cada endpoint.
Consulta não escreve; vendedor acessa somente vendas/clientes permitidos; gerente
não administra infraestrutura. admin-local é identidade de recuperação distinta.
Ocultar botões no dispositivo não substitui autorização backend.

As 25 permissões propostas no anexo foram preparadas na branch local de backend,
com teste de negação para Consulta e troca obrigatória da senha inicial. Serão
revisadas e integradas na v0.3.0 após testes transacionais reais.
