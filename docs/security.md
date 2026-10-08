# Segurança

Perfil atual é desenvolvimento sem credenciais reais no firmware. NVS é inicializada,
mas ainda não guarda senhas, tokens ou dados pessoais; NVS Encryption será validada
na v0.3.0 antes do provisionamento. Falha NVS não causa erase automático.
Não ativar eFuses, Secure Boot ou Flash Encryption neste perfil.

Identidades separadas: admin-local, administrador API, root SQL, usuário CRUD SQL,
usuário de migração. Sem senha universal. Gerador criptográfico no provisionamento,
hash Argon2id servidor e derivação adequada no dispositivo; pasta docs/private ignorada.
admin-local não recebe sessão ERP. Senhas/tokens não podem ficar no microSD.

HTTPS com CA/bundle, hostname e hora confiável; nunca desabilitar validação.
Cache minimiza dados pessoais e seu risco removível será tratado antes do uso.
Logs desta plataforma mostram somente estado/error/versão e não capturam o texto digitado.
O teste de escrita SD não garante resistência a remoção/queda de energia.

Servidor futuro: secrets por serviço, SQL interno, RBAC em cada endpoint, transações
ACID e idempotência no backend. Backups com acesso restrito e criptografia fora do host.
Controles e testes completos pertencem às etapas de infraestrutura/autenticação e
revisão v0.12.0. Nenhuma classificação de produção é dada nesta etapa.
