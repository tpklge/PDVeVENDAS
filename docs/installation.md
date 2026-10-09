# Instalação e atualização — TAB5 ERP 0.12.0

Servidor: OCI Ampere ARM64, Ubuntu com Docker Engine/Compose Plugin, Python 3 e
unzip. Traefik já instalado, provider Docker e rede externa meshcentral_proxy;
entrypoint websecure, resolver letsencrypt. Domínio da API:
https://tab5api.ampere.diadiatech.com.br, DNS apontando ao servidor. Portas 80/443
atendidas pelo Traefik; não publicar 3306/8000. Compose é para Docker Compose,
não Swarm. Ver [stack](../docker/README.md) e [Traefik](traefik.md).

## Instalação existente do usuário

A pasta `/home/ubuntu/TAB5_ERP` pode vir de ZIP, sem .git. Copie o pacote de
atualização do servidor para essa pasta. Faça primeiro a atualização do servidor:

```sh
cd /home/ubuntu/TAB5_ERP
unzip -o TAB5_ERP-v0.12.0-server-update.zip
bash docker/scripts/update-security.sh
bash docker/scripts/validate-security.sh
```

O script salva backup, constrói a API, para a versão anterior, aplica Alembic/seed,
recria e verifica a API. Preserva .env, secrets, usuários/senhas, banco, volume e
arquivos locais. Schema esperado: 008_offline. Não executar initialize novamente,
não reimportar schema.sql, não apagar volumes. Não depende de git no servidor.
O pacote é incremental; instalação vazia precisa do código completo abaixo.

## Servidor novo

Obtenha o **código completo** da branch release/v0.12.0-security no GitHub
[tpklge/PDVeVENDAS](https://github.com/tpklge/PDVeVENDAS/tree/release/v0.12.0-security)
e coloque em `/home/ubuntu/TAB5_ERP`. Deve incluir database/schema.sql,
database/initial_data.sql e docker/mariadb; o ZIP incremental não os substitui.

```sh
cd /home/ubuntu/TAB5_ERP
cp docker/.env.example docker/.env
chmod 600 docker/.env
chmod 755 docker/scripts/*.sh
docker network inspect meshcentral_proxy
bash docker/scripts/install.sh
bash docker/scripts/initialize.sh
docker compose --env-file docker/.env -f docker/compose.yaml exec api python -m app.cli reset-password --username admin
bash docker/scripts/validate-security.sh
```

Configure domínio/rede/entrypoint/resolver no .env antes de install se diferentes.
install gera secrets idempotentes e aplica migrações. initialize provisiona admin
somente numa base sem usuários; recusará modificar conta existente. reset-password
permite escolher senha ERP de oito ou mais caracteres, digitada sem eco, e revoga
sessões; evita digitar a senha inicial longa. Relatório inicial privado em
docs/private/INITIAL_CREDENTIALS.md nunca deve ser publicado. O PIN local do Tab5
é outra credencial escolhida no dispositivo.

Em volume vazio, hooks importam schema/initial_data e Alembic completa tabelas
comerciais. Em volume existente só migrações pendentes são aplicadas. Falha parcial
exige diagnóstico; não apagar uma base para tentar novamente.

## Tab5 / OTA

1. Preserve a pasta ERP do microSD, PIN e alimentação estável. Não formatar cartão.
2. Confira SHA-256 do BIN com o arquivo .sha256 fornecido; Linux usa sha256sum -c,
   macOS usa shasum -a256 -c, executados na pasta do BIN/sidecar.
3. Instale **TAB5_ERP-v0.12.0-app-OTA.bin** pelo M5Launcher já validado pelo usuário.
   É BIN da aplicação, sem erase/regravação de partições. Não instalar bootloader
   no lugar do aplicativo. Requisitos de build/partições em [hardware](hardware.md).
4. Instalação existente: desbloqueie pelo PIN de quatro números, aguarde conexão
   e faça login ERP com a senha atual. Configurações continuam no microSD.
5. Instalação nova: crie PIN local, configure SSID/senha e URL HTTPS, conecte;
   entre no ERP com admin e senha escolhida no servidor. Ver [Wi-Fi](wifi.md).
6. Abra Produtos e atualize cache. Cache é criptografado e incremental. Abrir offline
   permite consultas/rascunhos após login online inicial; fechar venda exige API.
7. Abra caixa, prepare venda, Revisar e cobrar, confira recebimento e confirme.
   Pagamentos são declarados pelo operador; não há emissão fiscal nem captura de
   cartão/Pix por adquirente nesta versão. Ver releases 0.7/0.9/0.11.

## Verificação e manutenção

Após OTA: desbloqueio/conexão/login, produto, venda única no caixa, reinício e
carregar rascunho salvo. Conferir tema e textos; não repetir venda de resultado
incerto com outra chave. Resolver consulta a tentativa original. Histórico de
etapas e limitações em [segurança](security.md) e [recuperação](recovery.md).

`bash docker/scripts/validate-release.sh` verifica persistência após recriação e
restaura backup em MariaDB **isolado**, com breve interrupção do serviço. Execute
quando a parada puder ocorrer. `validate-security.sh` verifica versão, isolamento,
HTTPS/cabeçalhos sem recriar banco nem testar transações em produção.

Backup: bash docker/scripts/backup.sh; mantenha cópia protegida fora do host.
Antes de apagar firmware/cartão, pare app pelo launcher e copie ERP inteira para
armazenamento protegido. Launcher não oferece backup automático. Recuperação de
base, epoch e pendências está em recovery.md; não restaurar backups antigos sobre
produção sem conciliar as operações posteriores.

Build do firmware: ESP-IDF 5.4.4, SDK/BSP fixados e Mbed TLS 3.6.7 preparado com
SHA-256 no diretório de build. Ver [desenvolvimento](development.md). USB só para
provisionamento técnico explícito; não é necessário no fluxo OTA existente.
