# API — contrato futuro

API FastAPI na nuvem OCI, atrás do Caddy; caminhos `/api/v1`, OpenAPI e JSON UTF-8.
Esta branch de plataforma não executa API. Versão mínima compatível não negociada ainda.

Obrigatórios na v0.2.0: `/health/live`, `/health/ready`, `/api/v1/system/status`.
Status público deve apresentar só versão/capabilities; detalhes de banco/migrações
somente em diagnóstico administrativo autorizado. Erros padronizados, correlação,
limites de corpo/paginação e tokens nunca presentes nos logs.

Na preparação local de backend, 10 testes de autenticação/infraestrutura passaram
em SQLite. Isso não valida MariaDB, deploy de containers ou integração com Tab5.
