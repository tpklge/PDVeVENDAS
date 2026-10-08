# Stack TAB5 ERP — Traefik existente

Execute no servidor OCI ARM64 com Docker Engine/Compose Plugin, Python 3 e a
rede existente `meshcentral_proxy`. O pacote inclui código da API, Dockerfile,
dependências fixadas, SQL e scripts. Não há imagem TAB5 publicada em registry;
o Compose constrói a imagem localmente no servidor.

Na raiz do projeto descompactado:

```sh
cp docker/.env.example docker/.env
chmod 600 docker/.env
python3 tools/generate_credentials.py --root .
docker network inspect meshcentral_proxy
docker compose --env-file docker/.env -f docker/compose.yaml config --quiet
docker compose --env-file docker/.env -f docker/compose.yaml up -d --build --wait --wait-timeout 240
docker compose --env-file docker/.env -f docker/compose.yaml ps -a
curl --fail --show-error https://tab5api.ampere.diadiatech.com.br/health/ready
```

O DNS deve apontar esse nome para o servidor atendido pelo Traefik. Conferir que
o Traefik usa o provider Docker, a rede `meshcentral_proxy`, o entrypoint
`websecure` e o resolver `letsencrypt` (grafia informada pelo usuário).
Os certificados continuam sob responsabilidade do Traefik existente.

Fluxo de inicialização:

1. MariaDB cria o banco UTF-8 e os usuários SQL de aplicação e migração.
2. Em volume vazio, importa `database/schema.sql` e `database/initial_data.sql`
   pelos hooks oficiais `/docker-entrypoint-initdb.d`, em ordem numérica.
3. O serviço `migrate` aguarda o banco saudável, aplica migrações pendentes e seed.
4. A API inicia somente após a conclusão bem-sucedida do serviço `migrate`.

Importação inicial não se repete em volume existente. Atualizações usam Alembic.
Uma falha parcial na importação exige diagnóstico/recuperação do banco antes de
reiniciar; não remover volumes com dados para tentar repetir a importação.
O schema entregue é a fundação de configuração/autenticação/RBAC/auditoria;
não inclui ainda as tabelas comerciais das etapas futuras do ERP.

API e MariaDB não publicam portas no host. Só a API entra na rede do Traefik;
o banco fica na rede backend interna. Credenciais são geradas no servidor,
montadas como secrets de arquivo e preservadas em reinicializações. O relatório
fica em `docs/private/INITIAL_CREDENTIALS.md`, fora do Git. O administrador de
API não é cadastrado automaticamente; o provisionamento é explícito:

```sh
docker/scripts/initialize.sh
```

Esse comando provisiona a base de autenticação; o firmware ainda não tem o
assistente/login da etapa 0.3.0. A senha local reservada pelo gerador também não
foi aplicada ao Tab5. A API inclui os endpoints de infraestrutura e a fundação
de autenticação; os módulos comerciais ainda não estão implementados.

Para diagnóstico interno e backup:

```sh
docker/scripts/check-health.sh
docker/scripts/backup.sh
```

Backups ficam em `docker/backups`; manter cópia protegida fora do servidor.
Para restauração, usar uma instância dedicada vazia, com as mesmas credenciais
SQL e schema compatível. O script exige `--confirm-replace`, interrompe a API e
importa o dump; não remove tabelas extras existentes. Não restaurar sobre uma
base divergente de produção. Executar migrações, validar e reativar a API após
restaurar. Backup/restauração real no MariaDB ainda precisam de validação.

No Portainer, o editor de stack sozinho não contém os arquivos locais nem o
contexto de build. Use o pacote completo no servidor e os comandos acima, ou
configure implantação pelo repositório com suporte a build e disponibilize os
arquivos de secrets e mounts no host do Docker. Este Compose é para Docker
Compose, não Swarm.

Validação local: 10 testes da API/fundação aprovados usando SQLite. Docker não
foi executado neste Mac e a stack não foi implantada no servidor nesta sessão.
O arquivo `compose.yaml` é completo; não é necessário acrescentar o complemento
anterior `compose.traefik.yaml`.
