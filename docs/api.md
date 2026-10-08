# API — infraestrutura e autenticação

API FastAPI implantada na nuvem OCI, atrás do Traefik existente; caminhos
`/api/v1`, OpenAPI e JSON UTF-8. API 0.2.0 é compatível com firmware 0.3.0 pelo
contrato `api_version=v1` e capabilities `auth`/`rbac`.

Implementados: `/health/live`, `/health/ready`, `/api/v1/system/status`.
Status público deve apresentar só versão/capabilities; detalhes de banco/migrações
somente em diagnóstico administrativo autorizado. Erros padronizados, correlação,
limites de corpo/paginação e tokens nunca presentes nos logs.

Autenticação implementada: POST `/api/v1/auth/login`, `/refresh`, `/logout`,
`/change-password` e GET `/api/v1/auth/me`. Access token opaco de 15 minutos;
refresh rotativo com limite de 8 horas, vinculado ao dispositivo. Replay revoga
a família. Troca de senha revoga sessões e exige novo login. Senhas Argon2id;
limite de falhas de login e mensagens sem exposição de credenciais.

GET `/api/v1/users`, `/roles` e `/permissions` exigem `users.read` e troca da
senha inicial concluída. Listas de usuários são paginadas. Não há endpoints
comerciais implementados. Provisionamento inicial pelo CLI no servidor.

11 testes locais atuais passam; CI da etapa 0.2.0 validou MariaDB/Docker reais
em AMD64/ARM64. O usuário comprovou HTTPS/health e backup no OCI. Integração
de login/Wi-Fi com o Tab5 permanece pendente de testes físicos da etapa 0.3.0.
