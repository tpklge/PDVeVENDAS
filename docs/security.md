# Segurança

O firmware candidato 0.3.1 salva todas as configurações locais em envelope
AES-256-GCM no microSD (`/ERP/config/settings.enc`). A chave é derivada da senha
admin-local com PBKDF2-HMAC-SHA256 e 200.000 iterações. Senha local mínima de 4
caracteres por escolha do usuário: senhas curtas oferecem menos resistência a
adivinhação offline de uma cópia do cartão. Não há configuração ERP na NVS;
Wi-Fi usa RAM. Ver [autenticação e backup](authentication.md).

Identidades separadas: admin-local, administrador API, root SQL, usuário CRUD SQL,
usuário de migração. Sem senha universal. Gerador criptográfico no provisionamento,
hash Argon2id servidor e derivação adequada no dispositivo; pasta docs/private ignorada.
admin-local não recebe sessão ERP. Tokens e senha ERP não são persistidos. Senha Wi-Fi fica apenas no envelope
criptografado do microSD; a senha local e a chave nunca são gravadas nele.

HTTPS com CA/bundle, hostname e hora confiável; nunca desabilitar validação.
Cache minimiza dados pessoais e seu risco removível será tratado antes do uso.
Logs desta plataforma mostram somente estado/error/versão e não capturam o texto digitado.
O teste de escrita SD não garante resistência a remoção/queda de energia.

Servidor futuro: secrets por serviço, SQL interno, RBAC em cada endpoint, transações
ACID e idempotência no backend. Backups com acesso restrito e criptografia fora do host.
Controles e testes completos pertencem às etapas de infraestrutura/autenticação e
revisão v0.12.0. Nenhuma classificação de produção é dada nesta etapa.
