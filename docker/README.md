# Stack TAB5 ERP — Traefik existente

Execute no servidor OCI ARM64 com Docker Engine/Compose Plugin, Python 3 e a
rede existente `meshcentral_proxy`. O pacote inclui código da API, Dockerfile,
dependências fixadas, SQL e scripts. Não há imagem TAB5 publicada em registry;
o Compose constrói a imagem localmente no servidor.
Instalação/atualização completas: [docs/installation.md](../docs/installation.md).

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
as tabelas comerciais são adicionadas pelas migrações até 008_offline.

API e MariaDB não publicam portas no host. Só a API entra na rede do Traefik;
o banco fica na rede backend interna. Credenciais são geradas no servidor,
montadas como secrets de arquivo e preservadas em reinicializações. O relatório
fica em `docs/private/INITIAL_CREDENTIALS.md`, fora do Git. O administrador de
API não é cadastrado automaticamente; o provisionamento é explícito:

```sh
docker/scripts/initialize.sh
```

Esse comando cria o admin apenas em instalação nova. O firmware inclui assistente,
PIN local, Wi-Fi e login ERP; o PIN é escolhido no Tab5. A API inclui produtos,
clientes/fornecedores, vendas, estoque, caixa, financeiro, relatórios e sincronização.
A senha ERP pode ser escolhida com CLI reset-password, sem exibir credenciais.

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
restaurar; renove epoch com invalidate-sync.sh antes de reativar produção.
Backup/restauração em MariaDB real passaram no CI e no OCI.

No Portainer, o editor de stack sozinho não contém os arquivos locais nem o
contexto de build. Use o pacote completo no servidor e os comandos acima, ou
configure implantação pelo repositório com suporte a build e disponibilize os
arquivos de secrets e mounts no host do Docker. Este Compose é para Docker
Compose, não Swarm.

Validação local 0.12: 68 testes API aprovados usando SQLite. CI com Docker
e MariaDB reais passou em AMD64 e ARM64, incluindo persistência e restauração.
O usuário comprovou implantação, HTTPS válido, persistência e restauração no OCI.
O script abaixo causa breve interrupção ao recriar os containers
e preserva o volume. Restaura o backup em banco temporário sem rede, compara
schema/dados, remove os recursos temporários e preserva o backup gerado.

```sh
bash docker/scripts/validate-release.sh
```

Docker não foi executado neste Mac.
O arquivo `compose.yaml` é completo; não é necessário acrescentar o complemento
anterior `compose.traefik.yaml`.
