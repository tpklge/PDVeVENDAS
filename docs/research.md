# Pesquisa técnica

Pesquisa em 08/10/2026. Decisões distinguem implementação atual e arquitetura alvo.

## Plataformas

ESP-IDF 5.4.4 está instalado e fixado; BSP oficial exige >=5.4. A documentação
`stable` hoje aponta para 6.1, portanto não deve ser usada como prova de que
APIs novas existem em 5.4.4. Consultar também a documentação versionada.
[ESP-IDF 5.4.4](https://docs.espressif.com/projects/esp-idf/en/v5.4.4/esp32p4/).
LVGL 9.3.0 e BSP 1.3.2 são dependências diretas; árvore exata será registrada
em `firmware/dependencies.lock`, sem wildcards no manifesto do aplicativo.
[LVGL](https://github.com/lvgl/lvgl), [ESP LVGL port](https://github.com/espressif/esp-bsp/tree/master/components/esp_lvgl_port).

[FATFS](https://docs.espressif.com/projects/esp-idf/en/stable/esp32p4/api-reference/storage/fatfs.html)
expõe VFS e SDMMC. Corrupção por energia/cartão removido exige testes; fsync e rename
não são garantia absoluta. Cache SQL local continua em avaliação: [atomic commit
SQLite](https://www.sqlite.org/atomiccommit.html) depende da implementação VFS e do
comportamento do armazenamento. JSON inicial é alternativa permitida, atrás de
interface de repositório, somente após testar recuperação e integridade.

[NVS Encryption](https://docs.espressif.com/projects/esp-idf/en/stable/esp32p4/api-reference/storage/nvs_encryption.html)
usa proteção das chaves e partições específicas. Não ativar eFuses na versão de
plataforma. Credenciais locais/tokens só serão provisionados após proteção validada.
[System time](https://docs.espressif.com/projects/esp-idf/en/stable/esp32p4/api-reference/system/system_time.html)
orienta relógio do SoC/SNTP. mbedTLS/esp_http_client integrarão certificate bundle
ou CA explícita, hostname, limite de resposta e timeout; [documentação](https://docs.espressif.com/projects/esp-idf/en/v5.4.4/esp32p4/api-reference/protocols/esp_http_client.html).

## Fluxos de comércio brasileiro

| Referência | Recursos usados como referência funcional |
|---|---|
| [Bling](https://ajuda.bling.com.br/hc/pt-br/sections/360005577073-Frente-de-Caixa) | Venda, troco, cliente opcional, sangria/suprimento, devolução, comprovante |
| [Omie.PDV](https://www.omie.com.br/omie-pdv/) | Frente de caixa ligada a estoque e financeiro |
| [MarketUP](https://suporte.marketup.com/hc/pt-br/articles/28376812781460-COMO-ACESSAR-O-PDV-OFFLINE) | Persistência local e sincronização explícita após desconexão |
| [ERP Olist, antigo Tiny](https://olist.com/sistema-erp/) | Cadastros, estoque central, pedidos e finanças |

Síntese de projeto: abrir caixa → montar carrinho por teclado → cliente opcional →
pagamentos declarados → confirmar transação no servidor → comprovante não fiscal.
Agrupar ações em poucas telas e priorizar pesquisa paginada, totais e atalhos.
Não reproduzir marcas, interface ou emissão fiscal destes sistemas. O offline
inicial não confirma vendas; recursos de contingência fiscal de terceiros não
se transferem automaticamente para este projeto.

## Servidor na nuvem

[MariaDB 11.8 LTS](https://mariadb.org/11-8-is-lts/) escolhido na preparação;
imagem oficial 11.8.8 verificada com manifests Linux AMD64 e ARM64.
[SQLAlchemy MariaDB](https://docs.sqlalchemy.org/en/20/dialects/mysql.html) permite
dialeto MariaDB com PyMySQL e parametrização SQL. [Alembic](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
será responsável por revisões; hooks de init não atualizam volumes existentes.
[GRANT](https://mariadb.com/docs/server/reference/sql-statements/account-management-sql-statements/grant)
permite separar CRUD da API e DDL das migrações, restritos ao schema do ERP.
[TLS MariaDB](https://mariadb.com/docs/server/security/securing-mariadb/encryption/data-in-transit-encryption/securing-connections-for-client-and-server)
será obrigatório entre hosts; no mesmo host, rede interna isolada sem publicação SQL.

[FastAPI](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/) fornece dependências
para autenticação; decisão inicial é sessão opaca revogável, não JWT sem estado.
Argon2id no servidor; papéis/permissões em tabelas e verificação backend.
[Caddy HTTPS](https://caddyserver.com/docs/automatic-https) exige domínio/DNS/portas
corretos. [Docker Compose secrets](https://docs.docker.com/compose/how-tos/use-secrets/)
são montagem por serviço, não cofre criptografado; proteger diretórios do host.

A preparação de backend permanece na branch local `work/backend-preparation`.
Seus pins e SQL serão revisados antes da v0.2.0; não representa deploy validado.
