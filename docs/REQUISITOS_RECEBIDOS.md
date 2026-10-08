# PROJETO: TAB5 ERP — Sistema de Gestão Comercial e PDV

## 1. OBJETIVO GERAL

Desenvolva um sistema de gestão comercial e controle de vendas, denominado **Tab5 ERP**, para execução nativa no M5Stack Tab5.

O projeto deverá implementar um ERP compacto, com características dos sistemas comerciais brasileiros, incorporando:

- Frente de caixa (PDV).
- Controle de vendas.
- Cadastro de produtos e serviços.
- Cadastro de clientes e fornecedores.
- Gestão de estoque.
- Controle financeiro básico.
- Abertura e fechamento de caixa.
- Registro de formas de pagamento.
- Relatórios gerenciais.
- Gestão de usuários e permissões.
- Login e autenticação.
- Painel administrativo.
- Configuração de Wi-Fi.
- Banco de dados principal hospedado na nuvem.
- Armazenamento local em microSD.
- Cache de consultas.
- Sincronização de informações.
- Operação em condições de conectividade intermitente.
- Sistema de instalação e configuração inicial.

O software deve apresentar uma interface profissional, intuitiva, rápida e inteiramente em português brasileiro.

A aplicação deverá funcionar em resolução de 1280×720 pixels, sempre no modo paisagem.

Não desenvolva apenas um protótipo visual. O objetivo é entregar uma aplicação efetivamente funcional, com persistência, validação das regras comerciais, controle de acesso e tratamento adequado dos erros.

### Princípios fundamentais

1. O sistema deve ser simples de utilizar.
2. A arquitetura deve permitir evolução sem reescrever módulos anteriores.
3. Os dados comerciais definitivos devem permanecer no banco central.
4. A ausência de conexão não deve provocar perda de dados locais.
5. A interface deve continuar responsiva durante operações de rede.
6. Toda operação comercial deve passar por validação de permissões.
7. Todas as operações de escrita devem preservar a integridade dos dados.
8. O projeto deve ser dividido em versões incrementais.
9. Cada versão deve possuir sua própria branch remota.
10. Todas as etapas devem incluir testes e documentação.
11. Os componentes devem ser compatíveis com a arquitetura ARM64 do servidor, quando aplicável.
12. O firmware deve poder ser utilizado pelo M5Launcher, quando sua arquitetura de carregamento permitir.

---

# 2. PESQUISA TÉCNICA OBRIGATÓRIA

Antes da implementação, pesquise e examine a documentação atual das tecnologias utilizadas.

## 2.1. Hardware

Investigue:

- M5Stack Tab5.
- ESP32-P4.
- ESP32-C6 integrado.
- Wi-Fi utilizando ESP-Hosted / esp_wifi_remote.
- LVGL.
- BSP oficial do Tab5.
- Tab5 Keyboard.
- microSD via SDMMC e FATFS.
- NVS e NVS Encryption.
- HTTPS por esp_http_client e mbedTLS.
- Configuração de hora por NTP e RTC.
- M5Launcher e seus requisitos de carregamento.

Documentação inicial:

https://docs.m5stack.com/en/core/Tab5

https://docs.m5stack.com/en/tab5/Tab5_Keyboard

https://docs.m5stack.com/en/arduino/projects/tab5/tab5_keyboard

https://docs.espressif.com/projects/esp-idf/en/stable/esp32p4/

https://github.com/espressif/esp-hosted-mcu

## 2.2. Sistemas de vendas brasileiros

Pesquise os recursos de sistemas como:

- Bling ERP.
- Omie ERP e Omie PDV.
- MarketUP.
- Tiny ERP ou seu equivalente atual.
- Outros sistemas brasileiros de pequeno comércio.

Identifique as funcionalidades comuns e os fluxos operacionais fundamentais.

Não copie interface, código, marcas ou recursos proprietários desses produtos. Utilize a pesquisa para orientar o levantamento funcional.

Priorize as funções que fazem sentido em uma tela de 5 polegadas com teclado físico.

## 2.3. Banco de dados e segurança

Pesquise especificamente:

- MariaDB em Docker.
- MariaDB LTS.
- TLS no MariaDB.
- Controle de acessos SQL.
- FastAPI.
- SQLAlchemy.
- Migrações com Alembic.
- Caddy e certificados HTTPS.
- Docker Compose.
- Secrets do Docker.
- SQLite em sistemas embarcados.
- Cache local e sincronização.
- Autenticação e RBAC.

Registre a versão exata e a origem de cada dependência escolhida.

Evite utilizar bibliotecas descontinuadas.

---

# 3. ARQUITETURA PRINCIPAL

A arquitetura deve conter três camadas.

## 3.1. Cliente embarcado

Aplicação C++ nativa executada no ESP32-P4.

Responsabilidades:

- Interface gráfica.
- Entrada pelo teclado.
- Configurações locais.
- Conexão Wi-Fi.
- Comunicação HTTPS.
- Autenticação do usuário.
- Cache local.
- Consultas e formulários.
- Armazenamento de operações pendentes.
- Exibição dos resultados retornados pela API.

O cliente não deve executar SQL diretamente no banco remoto.

## 3.2. API de aplicação

Servidor FastAPI executado em Docker.

Responsabilidades:

- Autenticação.
- Gestão das sessões.
- Autorização e permissões.
- Validação de dados.
- Regras comerciais.
- Transações de vendas.
- Movimentações de estoque.
- Controle de caixa.
- Gestão financeira.
- Consultas e relatórios.
- Sincronização.
- Auditoria.
- Comunicação com o MariaDB.

Utilizar SQLAlchemy com driver compatível com MariaDB.

Criar endpoints REST versionados, começando por `/api/v1`.

Gerar documentação OpenAPI.

## 3.3. Banco de dados central

Utilizar MariaDB, preferencialmente uma versão LTS estável com tag explicitamente fixada.

Utilizar a imagem Docker oficial.

O banco deverá:

- Persistir os dados em volume Docker.
- Utilizar InnoDB.
- Possuir índices adequados.
- Implementar integridade referencial.
- Suportar transações ACID.
- Utilizar usuários SQL com privilégios mínimos.
- Possuir backup e restauração documentados.
- Permanecer acessível somente na rede interna dos containers por padrão.

Não publicar a porta 3306 na internet.

O serviço público será a API HTTPS.

Se futuramente houver necessidade de conexão SQL remota para manutenção, documentar um procedimento separado utilizando túnel SSH ou conexão TLS validada com restrições de origem.

---

# 4. INFRAESTRUTURA DOCKER

Crie um diretório `/docker` com todos os arquivos necessários para subir o ambiente.

## 4.1. Serviços obrigatórios

O Docker Compose deverá conter:

**mariadb**

- Imagem oficial.
- Versão LTS fixada.
- Volume persistente.
- Usuário exclusivo da aplicação.
- Banco inicialmente denominado `tab5_erp`.
- Healthcheck.
- Política de reinicialização.
- Configuração de charset utf8mb4.
- Configuração de timezone adequada.
- Limites de recursos configuráveis.

**api**

- FastAPI.
- Conexão com MariaDB.
- Migrações de banco.
- Healthcheck.
- Logs.
- Configuração por arquivos e secrets.
- Execução sem privilégios elevados, quando viável.

**caddy**

- Reverse proxy.
- HTTPS.
- Redirecionamento de HTTP para HTTPS.
- Gerenciamento de certificados.
- Encaminhamento para a API.
- Logs de acesso com proteção de dados sensíveis.

## 4.2. Arquivos necessários

Produza:

```text
docker/
├── compose.yaml
├── .env.example
├── Caddyfile
├── api.Dockerfile
├── mariadb/
│   ├── conf.d/
│   │   └── server.cnf
│   └── init/
│       └── 001-initial.sql
├── scripts/
│   ├── install.sh
│   ├── initialize.sh
│   ├── migrate.sh
│   ├── backup.sh
│   ├── restore.sh
│   ├── check-health.sh
│   └── generate-secrets.sh
└── README.md
```

Os scripts devem ser executáveis e possuir tratamento de erros.

## 4.3. Inicialização automática

No primeiro `docker compose up -d`, o ambiente deverá ser capaz de:

1. Inicializar o banco.
2. Criar o schema.
3. Criar o usuário SQL da aplicação.
4. Aplicar as migrações iniciais.
5. Criar permissões padrão.
6. Preparar o processo de criação do administrador inicial.
7. Inicializar a API.
8. Inicializar o proxy HTTPS.
9. Expor um endpoint de verificação de saúde.

Não depender exclusivamente de arquivos montados em `/docker-entrypoint-initdb.d` para atualizações futuras, pois esses scripts não devem ser tratados como mecanismo de migração de bancos já inicializados.

Utilizar Alembic para migrações posteriores e manter os scripts SQL equivalentes no repositório.

A inicialização precisa ser idempotente, sem recriar dados ou sobrescrever credenciais a cada reinicialização.

## 4.4. Segurança do ambiente

Implementar:

- HTTPS obrigatório no acesso externo.
- TLS 1.2 ou superior, conforme suporte validado.
- Validação de certificados.
- Secrets para senhas de banco e chaves.
- Usuário SQL sem acesso de administrador.
- Senha root distinta.
- Rede interna Docker.
- Ausência de portas administrativas públicas.
- Rate limiting na autenticação.
- Proteção contra SQL Injection.
- Ausência de stack traces sensíveis nas respostas.
- Rotação de logs.
- Backups protegidos.
- Healthchecks.
- Política de atualização de dependências.

O usuário SQL da aplicação não deve poder criar usuários, alterar privilégios globais ou administrar o servidor.

O usuário de migração deve ser distinto e possuir privilégios adequados somente à atualização do schema.

Produza comandos verificáveis para demonstrar que a porta do MariaDB não está publicada.

## 4.5. Instalação em servidor

Documente a instalação em:

- Ubuntu Server.
- Debian.
- Docker Engine com Compose Plugin.
- Arquiteturas AMD64 e ARM64, quando suportadas pelas imagens escolhidas.

Inclua:

- Requisitos mínimos de CPU, memória e disco.
- Portas utilizadas.
- Configuração de domínio.
- DNS.
- Firewall.
- Comandos de instalação.
- Inicialização.
- Atualização.
- Backup.
- Restauração.
- Diagnóstico de problemas.

Estabeleça um perfil mínimo de testes para servidor pequeno, por exemplo, 2 vCPU, 2 GB de RAM e armazenamento persistente, sujeito a validação real de consumo.

Não apresente esse perfil como capacidade garantida sem medições.

---

# 5. SEGURANÇA DA COMUNICAÇÃO

A comunicação entre o Tab5 e o servidor deve ocorrer exclusivamente por HTTPS.

Utilizar esp_http_client com mbedTLS.

Requisitos:

1. Verificar a cadeia do certificado do servidor.
2. Verificar o hostname.
3. Não aceitar certificados indiscriminadamente.
4. Não desabilitar a verificação TLS para resolver erros de conexão.
5. Utilizar ESP Certificate Bundle ou CA explicitamente provisionada.
6. Suportar renovação de certificados.
7. Sincronizar a hora para validação TLS.
8. Implementar timeouts de conexão e leitura.
9. Implementar tentativas limitadas de reconexão.
10. Utilizar backoff exponencial.
11. Diferenciar erros de rede, TLS, autenticação e servidor.
12. Não registrar tokens ou senhas nos logs.
13. Impor tamanho máximo de respostas.
14. Validar JSON recebido.
15. Evitar bloquear a thread da interface gráfica.

A comunicação API–MariaDB poderá ocorrer pela rede interna isolada dos containers, sem publicação externa.

Quando for necessária conexão SQL entre hosts distintos, exigir TLS e verificação do servidor.

A API deve disponibilizar:

- `GET /health/live`
- `GET /health/ready`
- `GET /api/v1/system/status`

O endpoint público de status não pode revelar credenciais, configurações internas ou informações excessivas da infraestrutura.

---

# 6. INSTALAÇÃO INICIAL E ADMINISTRADOR LOCAL

Este é um requisito prioritário.

O aplicativo precisa possuir um sistema administrativo local, disponível diretamente no Tab5, mesmo antes de existir comunicação com a nuvem.

## 6.1. Primeiro boot

Quando não houver configuração inicial, abrir automaticamente um assistente de instalação.

Etapas:

**Etapa A — Preparação**

- Verificar hardware.
- Verificar teclado.
- Verificar touchscreen.
- Detectar cartão microSD.
- Verificar acesso aos arquivos.
- Inicializar as configurações locais.

**Etapa B — Wi-Fi**

- Pesquisar redes.
- Selecionar SSID.
- Informar senha.
- Estabelecer conexão.
- Exibir endereço IP.
- Exibir gateway e DNS.
- Testar acesso à internet.

**Etapa C — Servidor**

- Informar URL HTTPS da API.
- Configurar certificado CA, quando necessário.
- Testar DNS.
- Testar TLS.
- Testar endpoint de saúde.
- Consultar versão da API.
- Verificar compatibilidade com o firmware.

**Etapa D — Banco de dados**

- Verificar se a API consegue acessar o MariaDB.
- Consultar o estado das migrações.
- Identificar se o banco está inicializado.
- Exibir nome lógico da instalação e empresa.
- Permitir iniciar o provisionamento autorizado, quando aplicável.

Não solicitar a senha root do MariaDB no Tab5.

A criação física do banco, das tabelas e das credenciais SQL deverá ocorrer pelos scripts seguros do servidor.

O Tab5 poderá acionar, durante o provisionamento inicial, operações administrativas específicas da API mediante um token de instalação de uso único e curta duração.

Esse endpoint de provisionamento deve ser desativado após a instalação ou exigir procedimento explícito de reativação no servidor.

**Etapa E — Usuário administrador**

- Configurar ou ativar o administrador inicial da aplicação.
- Verificar que ele possui as permissões adequadas.
- Exigir alteração da senha inicial no primeiro acesso.

**Etapa F — Conclusão**

- Salvar as configurações locais.
- Validar conectividade.
- Abrir o menu principal.

## 6.2. Administrador local de recuperação

Criar uma identidade administrativa local chamada `admin-local`.

Ela deverá ser independente dos usuários comuns do ERP.

O administrador local poderá:

- Configurar Wi-Fi.
- Configurar endereço da API.
- Gerenciar certificados confiáveis.
- Testar conectividade.
- Verificar microSD.
- Limpar cache local.
- Inspecionar filas pendentes.
- Exportar logs sanitizados.
- Consultar versão do firmware.
- Restaurar configurações de rede.
- Executar diagnóstico.
- Restaurar configurações do aplicativo, mediante confirmação.
- Reiniciar o dispositivo.

A conta `admin-local` não deve conseguir visualizar vendas ou acessar funções comerciais protegidas sem autenticação válida no servidor.

Uma senha local não deve equivaler a uma sessão administrativa remota.

## 6.3. Geração das senhas iniciais

Crie um procedimento para gerar senhas aleatórias criptograficamente fortes.

Gerar senhas distintas para:

- Administrador local do Tab5.
- Administrador inicial da API.
- Root do MariaDB.
- Usuário SQL da aplicação.
- Usuário SQL de migrações, quando necessário.

Utilizar gerador aleatório criptograficamente seguro.

Para senhas humanas, gerar pelo menos 20 caracteres aleatórios ou força equivalente.

Gerar as credenciais no momento do provisionamento, sem utilizar senhas constantes compiladas no firmware.

Registrar a senha inicial administrativa em:

`docs/private/INITIAL_CREDENTIALS.md`

Este arquivo deverá conter:

- Nome da instalação.
- Identificador da credencial.
- Usuário.
- Senha inicial.
- Data de geração.
- Procedimento para troca.
- Procedimento de recuperação.

O arquivo deverá ser gerado localmente e protegido por permissões de acesso do sistema operacional.

Adicionar `docs/private/` ao `.gitignore`.

**NUNCA realizar commit desse arquivo, mesmo em repositórios privados.**

Na documentação pública, incluir apenas `INITIAL_CREDENTIALS.example.md`, sem credenciais reais.

Não incluir senhas em README, exemplos de código, logs ou commits.

Armazenar o verificador da senha local utilizando algoritmo adequado de derivação de chave, salt individual e comparação segura.

Investigar o uso de NVS Encryption no ESP32-P4.

## 6.4. Alteração e recuperação

Implementar:

- Alteração de senha local.
- Limite de tentativas.
- Espera progressiva após falhas.
- Recuperação física mediante procedimento explícito.
- Exclusão segura das credenciais locais durante restauração.
- Aviso claro antes de operações destrutivas.

Nunca implementar senha mestre universal no firmware.

---

# 7. USUÁRIOS, LOGIN E PERMISSÕES

## 7.1. Login

Criar tela de autenticação com:

- Usuário ou e-mail.
- Senha.
- Mostrar/ocultar senha.
- Entrar.
- Informações de conectividade.
- Indicador de servidor acessível.
- Recuperação de senha, quando configurada.

Os dados de autenticação serão validados pela API.

Armazenar senhas no servidor usando Argon2id, com parâmetros adequados.

Nunca armazenar senhas em texto puro.

## 7.2. Sessões

Implementar:

- Access token com duração curta.
- Renovação controlada da sessão.
- Refresh token rotativo ou mecanismo equivalente.
- Logout.
- Expiração de sessão.
- Revogação administrativa.
- Identificação do dispositivo.
- Bloqueio de usuários inativos.
- Registro de tentativas de login.

Tokens persistidos no dispositivo devem receber proteção compatível com o hardware.

Nunca utilizar o microSD como repositório de tokens não criptografados.

## 7.3. Perfis iniciais

Criar quatro perfis:

**Administrador**

Acesso completo às funcionalidades comerciais e de gestão de usuários.

**Gerente**

- Produtos.
- Estoque.
- Clientes.
- Vendas.
- Descontos autorizados.
- Cancelamentos.
- Relatórios.
- Gestão de caixa.

Não possui acesso às configurações sensíveis da infraestrutura.

**Vendedor**

- Consultar produtos.
- Consultar clientes permitidos.
- Criar vendas.
- Consultar suas vendas.
- Emitir comprovantes não fiscais.
- Operar seu caixa quando autorizado.

**Consulta**

- Visualizar os cadastros e relatórios expressamente autorizados.
- Não alterar dados.

## 7.4. Permissões granulares

Criar RBAC com tabelas específicas de usuários, papéis, permissões e relacionamentos.

Exemplos:

```text
products.read
products.create
products.update
products.delete

customers.read
customers.create
customers.update

sales.read
sales.create
sales.cancel
sales.discount

inventory.read
inventory.adjust

cash.open
cash.close
cash.withdraw
cash.deposit

reports.read
reports.financial

users.read
users.create
users.update
users.disable

settings.read
settings.update
```

Permitir futuramente configurar papéis personalizados.

As permissões devem ser verificadas na API, e não somente escondendo botões na interface.

Registrar as operações administrativas em auditoria.

---

# 8. INTERFACE GRÁFICA DO TAB5

## 8.1. Requisitos

A interface deverá ser desenvolvida com LVGL, utilizando 1280×720 pixels.

Priorizar:

- Design limpo.
- Fontes legíveis.
- Contraste adequado.
- Navegação por teclado.
- Suporte a touchscreen.
- Formulários simples.
- Botões suficientemente grandes.
- Baixa latência.
- Indicação de carregamento.
- Mensagens objetivas.
- Consistência visual.

Criar dois temas:

- Claro.
- Escuro.

## 8.2. Tela inicial

Após autenticação, apresentar:

**TAB5 ERP**

Painel com cartões:

- Nova venda.
- Produtos.
- Clientes.
- Estoque.
- Caixa.
- Financeiro.
- Relatórios.
- Configurações.

Na região superior:

- Usuário conectado.
- Data e hora.
- Status do Wi-Fi.
- Status do servidor.
- Situação da sincronização.

Na região inferior:

- Versão do sistema.
- Última sincronização.
- Operações pendentes.

## 8.3. Navegação pelo teclado

Implementar:

- Setas para seleção.
- Enter para confirmação.
- Esc para voltar.
- Tab para próximo campo.
- Shift+Tab para campo anterior.
- F1 para ajuda.
- F2 para nova venda.
- F3 para produtos.
- F4 para clientes.
- F5 para atualizar consultas.
- F10 para finalizar venda, quando permitido.

Validar o comportamento real das teclas no Tab5 Keyboard.

A implementação deve utilizar corretamente I²C, interrupções e os modos de funcionamento suportados pelo teclado.

Não depender de teclado virtual para executar atividades comuns.

## 8.4. Entrada de dados

Garantir suporte a:

- Letras maiúsculas e minúsculas.
- Números.
- Símbolos.
- Senhas.
- CPF e CNPJ.
- Valores monetários.
- Quantidades.
- Datas.
- Campos de pesquisa.

Implementar máscaras e validação quando necessário.

O touchscreen poderá abrir um teclado virtual se o teclado físico não estiver conectado.

---

# 9. MÓDULO DE PRODUTOS

Criar cadastro com:

- ID interno.
- Código SKU.
- Código de barras GTIN/EAN opcional.
- Nome.
- Descrição.
- Categoria.
- Unidade de medida.
- Preço de custo.
- Preço de venda.
- Estoque atual.
- Estoque mínimo.
- Estoque máximo opcional.
- Status ativo/inativo.
- Data de cadastro.
- Data de alteração.

Campos fiscais opcionais, sem implementação automática de regras tributárias:

- NCM.
- CEST.
- Origem.
- Dados tributários a serem detalhados futuramente.

Permitir:

- Criar produto.
- Alterar produto.
- Consultar produto.
- Inativar produto.
- Pesquisar pelo nome.
- Pesquisar pelo código.
- Pesquisar pelo código de barras.
- Filtrar por categoria.
- Consultar disponibilidade.
- Identificar estoque baixo.

Utilizar paginação nas consultas.

Não carregar milhares de produtos simultaneamente na memória do Tab5.

Validar códigos duplicados no servidor.

Usar exclusão lógica para produtos referenciados por vendas, preservando o histórico.

---

# 10. MÓDULO DE CLIENTES

Criar cadastro com:

- ID interno.
- Nome.
- Tipo de pessoa.
- CPF ou CNPJ, opcional.
- Telefone.
- E-mail.
- Endereço.
- Cidade.
- UF.
- CEP.
- Observações.
- Status.
- Datas de criação e alteração.

Permitir:

- Novo cliente.
- Consultar.
- Alterar.
- Inativar.
- Pesquisar pelo nome.
- Pesquisar pelo CPF/CNPJ quando autorizado.
- Visualizar histórico de compras.
- Visualizar valores e datas das compras.

Permitir vendas para consumidor não identificado.

Aplicar os princípios de minimização de dados da LGPD.

Não exigir CPF para operações em que sua coleta não seja necessária.

Limitar a quantidade de dados pessoais mantidos no cache do microSD.

---

# 11. MÓDULO DE FORNECEDORES

Criar cadastro básico com:

- Nome ou razão social.
- Nome fantasia.
- CNPJ opcional.
- Telefone.
- E-mail.
- Endereço.
- Contato.
- Observações.
- Status.

Permitir associar fornecedores a produtos e entradas de estoque.

Preparar estrutura para futuras compras e pedidos de reposição.

---

# 12. FRENTE DE CAIXA / PDV

Este é o módulo central.

Criar uma interface de venda rápida, adequada ao teclado e à tela do Tab5.

## 12.1. Fluxo de venda

O operador deverá conseguir:

1. Abrir uma nova venda.
2. Identificar um cliente, opcionalmente.
3. Pesquisar produtos.
4. Adicionar itens.
5. Informar quantidades.
6. Alterar quantidades.
7. Remover itens.
8. Visualizar subtotal.
9. Aplicar desconto autorizado.
10. Selecionar pagamento.
11. Confirmar a venda.
12. Receber confirmação do servidor.
13. Emitir comprovante não fiscal ou disponibilizar resumo.
14. Iniciar nova venda.

## 12.2. Carrinho

Cada item deve conter:

- Produto.
- Quantidade.
- Preço unitário.
- Desconto.
- Subtotal.

Exibir o total continuamente.

Preservar os preços efetivamente praticados na venda, mesmo que o preço do cadastro seja posteriormente alterado.

## 12.3. Descontos

Permitir:

- Desconto percentual.
- Desconto em valor.
- Desconto por item.
- Desconto no total.

Implementar limites de desconto conforme perfil de usuário.

Descontos acima do limite exigem autorização de perfil adequado.

A autorização deve ser validada no servidor.

Não confiar no valor final calculado pelo dispositivo sem validação.

## 12.4. Formas de pagamento

Implementar registro de:

- Dinheiro.
- Pix.
- Cartão de débito.
- Cartão de crédito.
- Transferência.
- Outros.

Permitir pagamento misto, por exemplo:

- Parte em dinheiro.
- Parte em Pix.

Para dinheiro, calcular o troco.

A versão inicial apenas registra pagamentos informados pelo operador.

Não afirmar que um Pix foi liquidado sem integração e confirmação de um prestador de serviços de pagamento.

Não armazenar números completos de cartões, CVV ou dados sensíveis de pagamento.

Deixar preparada a arquitetura para futura integração com TEF e provedores Pix.

## 12.5. Integridade transacional

A confirmação de uma venda deve ocorrer dentro de uma transação de banco.

A operação precisa executar atomicamente:

1. Validar usuário.
2. Validar permissão.
3. Validar itens.
4. Verificar preços aplicáveis.
5. Verificar descontos.
6. Verificar disponibilidade de estoque.
7. Criar cabeçalho da venda.
8. Criar itens.
9. Registrar pagamentos declarados.
10. Registrar movimentações de estoque.
11. Atualizar saldos.
12. Registrar auditoria.
13. Confirmar a transação.

Se alguma operação falhar, executar rollback completo.

Utilizar bloqueios transacionais apropriados, como SELECT FOR UPDATE ou estratégia equivalente, para evitar venda simultânea que provoque saldo incorreto.

Toda solicitação de criação de venda deve ter chave de idempotência.

Se o dispositivo reenviar uma venda após timeout, o servidor deverá retornar o resultado da transação anterior, sem registrar outra venda.

---

# 13. CANCELAMENTOS E DEVOLUÇÕES

Permitir:

- Cancelamento autorizado.
- Devolução total.
- Devolução parcial.
- Registro de justificativa.
- Identificação do responsável.
- Reposição de estoque quando aplicável.
- Estorno gerencial de valores.
- Registro em auditoria.

Nunca simplesmente apagar uma venda finalizada.

Preservar o histórico de operações.

Distinguir cancelamento comercial de cancelamento fiscal.

Não afirmar que pagamentos externos foram efetivamente estornados sem integração com o prestador correspondente.

---

# 14. GESTÃO DE ESTOQUE

Implementar controle básico de movimentação.

Tipos:

- Entrada por compra.
- Entrada por ajuste.
- Saída por venda.
- Saída por ajuste.
- Devolução.
- Correção autorizada.

Cada movimentação deverá conter:

- Produto.
- Tipo.
- Quantidade.
- Saldo anterior.
- Saldo posterior.
- Origem.
- Usuário responsável.
- Data e hora.
- Justificativa quando necessária.

Funcionalidades:

- Consultar estoque.
- Ajustar estoque.
- Registrar entrada.
- Consultar histórico.
- Listar estoque baixo.
- Visualizar produtos sem estoque.

Não permitir edição direta do saldo sem registrar movimentação correspondente.

Configurar política de estoque negativo, inicialmente desativada.

Manter consistência em acessos concorrentes.

---

# 15. CONTROLE DE CAIXA

Implementar caixa por operador ou terminal.

## 15.1. Abertura

Campos:

- Identificador do caixa.
- Operador.
- Data e hora.
- Valor inicial.
- Observação.

Não permitir abertura duplicada de sessão de caixa incompatível com as regras configuradas.

## 15.2. Movimentações

Registrar:

- Recebimento de venda.
- Suprimento.
- Sangria.
- Ajuste autorizado.

Diferenciar valores em dinheiro de outros meios de pagamento.

## 15.3. Fechamento

Exibir:

- Saldo inicial.
- Total de vendas.
- Total recebido por forma de pagamento.
- Sangrias.
- Suprimentos.
- Saldo esperado.
- Saldo informado.
- Diferença.
- Operador.
- Data e hora.

Exigir justificativa para diferenças relevantes.

Permitir fechamento apenas ao operador autorizado.

Registrar histórico e auditoria.

---

# 16. FINANCEIRO BÁSICO

Implementar:

- Contas a receber.
- Contas a pagar.
- Lançamentos financeiros.
- Categorias de receitas.
- Categorias de despesas.
- Datas de vencimento.
- Baixas manuais.
- Situação de pagamento.
- Consultas por período.

Na primeira implementação, não é necessário integração bancária.

Criar estrutura preparada para evolução futura.

Evitar confundir:

- Venda realizada.
- Pagamento declarado.
- Recebimento efetivo.
- Valor a receber.
- Receita gerencial.

As regras devem estar documentadas.

---

# 17. RELATÓRIOS

Implementar relatórios consultados por meio da API.

Relatórios iniciais:

- Vendas do dia.
- Vendas por período.
- Vendas por vendedor.
- Vendas por produto.
- Produtos mais vendidos.
- Vendas por forma de pagamento.
- Estoque atual.
- Produtos abaixo do mínimo.
- Histórico de movimentações.
- Resumo de caixa.
- Cancelamentos.
- Contas a receber.

Exibir:

- Totais.
- Quantidades.
- Períodos.
- Agrupamentos relevantes.

Utilizar paginação ou agregações no servidor.

Não transferir milhares de registros ao dispositivo para calcular totais localmente.

Permitir exportação CSV pela API em uma etapa posterior.

---

# 18. DOCUMENTOS FISCAIS

Projetar o sistema considerando o cenário brasileiro, mas separar o registro gerencial de vendas da emissão fiscal.

Preparar modelos de dados para futuras integrações com:

- NFC-e.
- NF-e.
- NFS-e, se futuramente necessário.

A integração fiscal real dependerá das regras aplicáveis, documentação técnica, credenciamento, certificado digital e serviços autorizadores.

Não desenvolver uma suposta NFC-e válida usando apenas um PDF ou layout de comprovante.

A primeira versão poderá produzir somente um **comprovante não fiscal**, devidamente identificado.

Criar interfaces de integração para provedores fiscais futuros.

Documentar que o sistema, enquanto não possuir integração fiscal validada, não substitui as obrigações fiscais da empresa.

---

# 19. BANCO DE DADOS — MODELO SQL

Crie um schema MariaDB normalizado.

Utilizar:

- InnoDB.
- utf8mb4.
- Chaves primárias.
- Chaves estrangeiras.
- Índices.
- Restrições UNIQUE.
- NOT NULL quando apropriado.
- Campos de auditoria.
- Tipos numéricos apropriados.
- Relacionamentos consistentes.

Utilizar DECIMAL para valores monetários no banco.

Não utilizar FLOAT ou DOUBLE para representar dinheiro.

No cliente embarcado, preferir valores monetários em centavos inteiros, respeitando os requisitos de conversão e arredondamento.

A API deve trabalhar com tipos decimais exatos e serialização consistente.

## 19.1. Tabelas obrigatórias

Criar pelo menos:

```text
companies
app_settings
devices

users
roles
permissions
user_roles
role_permissions
sessions
auth_audit

categories
units
products
product_prices

customers
suppliers

warehouses
stock_balances
stock_movements

sales
sale_items
sale_payments
sale_cancellations
sale_returns
sale_return_items

payment_methods

cash_registers
cash_sessions
cash_movements

financial_categories
accounts_receivable
accounts_payable
financial_transactions

sync_operations
idempotency_keys

audit_logs
schema_migrations
```

É permitido complementar o modelo com outras tabelas quando houver justificativa técnica.

A primeira versão deverá suportar uma empresa, mas o modelo poderá ser preparado para expansão futura, sem introduzir multiempresa complexo e desnecessário no MVP.

## 19.2. Requisitos SQL

Cada tabela precisa possuir:

- Nome consistente.
- Tipos corretos.
- Restrições.
- Relacionamentos.
- Índices úteis.
- Campos de criação e atualização quando pertinentes.

As tabelas operacionais devem manter associação com usuário ou dispositivo quando necessário.

A tabela de auditoria deve registrar:

- Ator.
- Operação.
- Entidade.
- Identificador do registro.
- Data.
- Resultado.
- Origem ou dispositivo.
- Informações mínimas necessárias ao rastreamento.

Não armazenar senhas ou tokens nesses registros.

## 19.3. Scripts

Gerar:

```text
database/
├── schema.sql
├── initial_data.sql
├── indexes.sql
├── permissions.sql
├── migrations/
│   ├── V001__initial.sql
│   ├── V002__products.sql
│   └── ...
├── tests/
└── README.md
```

`schema.sql` deve representar integralmente o schema da versão documentada.

As migrações deverão ser consistentes com o modelo SQLAlchemy e com o schema distribuído.

Gerar dados iniciais:

- Papéis padrão.
- Permissões.
- Formas de pagamento.
- Unidades de medida.
- Categorias financeiras básicas.

Não inserir contas administrativas com senhas fixas.

Criar script seguro para provisionar a primeira conta administrativa.

## 19.4. Importação

Documentar:

- Como criar o banco.
- Como importar o schema.
- Como importar dados iniciais.
- Como verificar tabelas.
- Como executar migrações.
- Como diagnosticar erros.
- Como realizar backup.
- Como restaurar backup.
- Como atualizar de uma versão para outra.

Testar os scripts em um banco vazio e em um banco já existente, com dados de teste.

---

# 20. API REST

Criar endpoints versionados.

Exemplos:

```text
POST   /api/v1/auth/login
POST   /api/v1/auth/refresh
POST   /api/v1/auth/logout
GET    /api/v1/auth/me

GET    /api/v1/products
GET    /api/v1/products/{id}
POST   /api/v1/products
PATCH  /api/v1/products/{id}

GET    /api/v1/customers
POST   /api/v1/customers
PATCH  /api/v1/customers/{id}

GET    /api/v1/sales
POST   /api/v1/sales
GET    /api/v1/sales/{id}
POST   /api/v1/sales/{id}/cancel

GET    /api/v1/inventory
POST   /api/v1/inventory/adjustments

POST   /api/v1/cash/open
POST   /api/v1/cash/close
POST   /api/v1/cash/movements

GET    /api/v1/reports/daily-sales
GET    /api/v1/reports/stock
GET    /api/v1/reports/cash

GET    /api/v1/users
POST   /api/v1/users
PATCH  /api/v1/users/{id}

GET    /api/v1/roles
GET    /api/v1/permissions

GET    /api/v1/sync/catalog
POST   /api/v1/sync/operations

GET    /api/v1/system/status
```

Implementar respostas JSON consistentes.

Os erros devem utilizar códigos HTTP apropriados.

Definir formato padronizado de erros contendo código de aplicação, mensagem amigável e identificador de rastreamento.

Usar identificadores de correlação para diagnosticar transações entre cliente e servidor.

Todos os endpoints protegidos devem validar autenticação e autorização no backend.

Validar tamanho de payload, paginação, parâmetros e campos.

Documentar exemplos de request e response.

---

# 21. BANCO DE DADOS LOCAL NO MICROSD

Implementar cache persistente para reduzir consultas à API e permitir acesso rápido aos dados.

O diretório obrigatório será:

`/ERP`

na raiz do cartão microSD.

No ESP-IDF, o caminho poderá corresponder a:

`/sdcard/ERP`

conforme a montagem do sistema de arquivos.

## 21.1. Tecnologia

Investigue a viabilidade de utilizar SQLite embarcado no ESP32-P4, armazenado no microSD.

Preferência:

`/ERP/cache/erp_cache.db`

O SQLite deve ser utilizado exclusivamente para dados locais, sem conexão direta ao banco remoto.

Se a integração da biblioteca SQLite causar incompatibilidade ou complexidade desproporcional, implemente inicialmente um repositório baseado em JSON estruturado, com índices em memória e escrita controlada.

Nesse caso, documente a decisão e mantenha uma interface abstrata que permita migrar para SQLite futuramente.

Não implemente um parser SQL próprio.

## 21.2. Estrutura local

Criar:

```text
/ERP/
├── cache/
│   └── erp_cache.db
├── sync/
│   ├── queue/
│   └── state.json
├── logs/
├── exports/
├── backups/
└── version.json
```

Caso seja adotado armazenamento JSON, adequar os arquivos ao mesmo modelo lógico.

Não colocar credenciais em texto simples nesses diretórios.

## 21.3. Dados em cache

Manter somente os dados necessários:

- Produtos.
- Categorias.
- Preços.
- Estoque consultado.
- Configurações não sensíveis.
- Referências de clientes autorizadas.
- Metadados de sincronização.

As consultas de produtos devem ser possíveis sem solicitar novamente todos os dados à API.

Criar sistema de invalidação e atualização incremental do cache.

Cada registro poderá conter:

- Identificador remoto.
- Versão.
- Data da última atualização.
- Origem.
- Estado de sincronização.

Não tratar estoque consultado anteriormente como saldo definitivamente atual.

## 21.4. Escrita segura

Implementar:

- Escrita temporária seguida de substituição controlada.
- Validação de integridade.
- Recuperação após interrupção.
- Tratamento de remoção inesperada do cartão.
- Verificação de espaço disponível.
- Limites para o crescimento dos logs.
- Estratégia de recuperação de arquivos corrompidos.

Considerar as limitações de FATFS e do microSD, incluindo a ausência de garantias absolutas contra corrupção após perda repentina de energia.

## 21.5. Ausência de microSD

O sistema deverá:

- Inicializar normalmente.
- Avisar que o armazenamento local está indisponível.
- Continuar operando online quando possível.
- Desativar funcionalidades que dependam de fila persistente.
- Evitar armazenar operações financeiras pendentes exclusivamente em RAM.

As configurações essenciais de inicialização deverão ficar na memória interna protegida do dispositivo.

---

# 22. CONECTIVIDADE WI-FI

Implementar gerenciamento completo de Wi-Fi.

## 22.1. Configuração

O menu deve permitir:

- Ativar Wi-Fi.
- Pesquisar redes.
- Mostrar intensidade do sinal.
- Selecionar SSID.
- Informar senha.
- Salvar rede.
- Esquecer rede.
- Reconectar.
- Consultar IP.
- Consultar gateway.
- Consultar DNS.
- Testar acesso ao servidor.

Priorizar DHCP.

IP estático poderá ser adicionado posteriormente.

## 22.2. Integração real do Tab5

O ESP32-P4 não possui rádio Wi-Fi próprio.

O Tab5 utiliza ESP32-C6 integrado, conectado ao processador principal por SDIO.

Investigar e utilizar corretamente ESP-Hosted e/ou esp_wifi_remote, conforme o BSP escolhido.

Não escrever código baseado na suposição de que o P4 é equivalente a um ESP32-S3 com Wi-Fi interno.

## 22.3. Reconexão

Implementar:

- Reconexão automática.
- Indicador visual de conexão.
- Diagnóstico de DNS.
- Diagnóstico de TLS.
- Detecção de perda de conectividade.
- Recuperação sem reiniciar todo o sistema.
- Timeout de operações.
- Retomada da sincronização.

A interface não pode ficar congelada durante tentativas de conexão.

---

# 23. SINCRONIZAÇÃO E MODO OFFLINE

Implementar a sincronização de forma incremental.

## 23.1. Primeira versão

Permitir consultas a produtos e dados não sensíveis armazenados no cache, com indicação de que podem estar desatualizados.

Se não houver conectividade, bloquear a confirmação definitiva de vendas.

O sistema poderá manter um carrinho ou rascunho local, mas não deverá marcar a venda como concluída sem confirmação do backend.

## 23.2. Versão posterior — fila offline

Implementar fila persistente de operações comerciais pendentes, quando a estrutura de sincronização estiver testada.

Cada operação terá:

- UUID global.
- Tipo.
- Dados necessários.
- Data local.
- Identificador de dispositivo.
- Identificador de usuário.
- Estado.
- Número de tentativas.
- Último erro.
- Chave de idempotência.

Estados:

- PENDENTE.
- ENVIANDO.
- CONFIRMADA.
- REJEITADA.
- CONFLITO.
- REQUER_INTERVENCAO.

## 23.3. Segurança da sincronização

Não executar vendas pendentes usando uma sessão inválida ou usuário sem permissão.

Se a sessão expirar, reautenticar antes de sincronizar.

O backend será a autoridade final sobre:

- Estoque.
- Preço.
- Permissões.
- Regras de desconto.
- Situação do caixa.
- Status da venda.

Caso exista conflito, apresentar o problema ao operador e exigir resolução apropriada.

Não usar política de sobrescrever cegamente os dados do servidor.

Não garantir conclusão de venda offline quando não houver estoque reservado.

Não eliminar automaticamente registros pendentes em caso de falha.

Permitir auditoria e inspeção das operações.

## 23.4. Evitar duplicidade

O servidor deve reconhecer solicitações já processadas.

Uma operação com a mesma chave de idempotência não deve produzir uma segunda venda.

Persistir o resultado associado à chave de idempotência.

Testar interrupções de conexão após o commit do banco e antes do recebimento da resposta.

## 23.5. Consistência

Implementar sincronização incremental de catálogos usando cursor ou versão de alteração no servidor.

Evitar depender somente do relógio do dispositivo para detectar atualizações.

---

# 24. CONFIGURAÇÕES GERAIS

Criar menu administrativo com:

**Dispositivo**

- Nome do terminal.
- ID do terminal.
- Versão.
- Brilho.
- Data e hora.
- Estado do microSD.
- Espaço disponível.

**Rede**

- Wi-Fi.
- IP.
- Servidor DNS.
- URL da API.
- Teste de conectividade.

**Sistema**

- Tema.
- Idioma pt-BR.
- Atualização do cache.
- Limpeza de cache.
- Logs.
- Diagnóstico.
- Sincronização.

**ERP**

- Dados da empresa.
- Configurações comerciais autorizadas.
- Perfil de caixa.
- Regras de operação.
- Tabela de preços padrão.

**Segurança**

- Troca de senha local.
- Bloqueio automático.
- Tempo de sessão.
- Certificados confiáveis.
- Informações de segurança.

Proteger cada operação conforme sua natureza.

---

# 25. DATAS, VALORES E PADRÕES BRASILEIROS

Aplicar:

- Idioma português brasileiro.
- Moeda BRL.
- Exibição monetária `R$ 1.234,56`.
- Datas no formato `DD/MM/AAAA`.
- Horas em formato de 24 horas.
- Validação de CPF e CNPJ quando preenchidos.
- CEP brasileiro.
- Unidades de medida comuns no comércio brasileiro.

O servidor deverá armazenar timestamps de maneira consistente, preferencialmente em UTC.

A aplicação deverá converter as datas para o fuso configurado, inicialmente `America/Cuiaba`.

Não presumir que o banco e o dispositivo utilizam a mesma configuração de fuso.

Documentar as regras de arredondamento monetário.

---

# 26. AUDITORIA

Implementar registro de eventos relevantes:

- Login.
- Logout.
- Falha de login.
- Criação de usuário.
- Mudança de permissão.
- Alteração de preço.
- Ajuste de estoque.
- Venda concluída.
- Cancelamento.
- Devolução.
- Abertura de caixa.
- Sangria.
- Fechamento de caixa.
- Alteração de configurações.

Registrar identificador de usuário, dispositivo e correlação quando aplicável.

Não registrar senhas, tokens ou dados de cartões.

Proteger os logs contra alteração por usuários comuns.

A auditoria deve permitir identificar alterações importantes sem depender exclusivamente dos logs do dispositivo.

---

# 27. ARQUITETURA DO CÓDIGO

Organize o projeto em módulos independentes.

Estrutura sugerida:

```text
Tab5-ERP/
├── README.md
├── CHANGELOG.md
├── VERSION
├── .gitignore
├── .github/
│   └── workflows/
├── firmware/
│   ├── CMakeLists.txt
│   ├── sdkconfig.defaults
│   ├── partitions.csv
│   ├── main/
│   ├── components/
│   │   ├── display/
│   │   ├── keyboard/
│   │   ├── wifi_manager/
│   │   ├── api_client/
│   │   ├── auth_client/
│   │   ├── local_admin/
│   │   ├── storage/
│   │   ├── synchronization/
│   │   └── ui/
│   └── screens/
│       ├── setup/
│       ├── login/
│       ├── dashboard/
│       ├── products/
│       ├── customers/
│       ├── sales/
│       ├── inventory/
│       ├── cash/
│       ├── finance/
│       └── reports/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   ├── repositories/
│   │   ├── security/
│   │   └── core/
│   ├── alembic/
│   ├── tests/
│   └── requirements.txt
├── database/
│   ├── schema.sql
│   ├── initial_data.sql
│   ├── migrations/
│   └── README.md
├── docker/
│   ├── compose.yaml
│   ├── Caddyfile
│   ├── api.Dockerfile
│   ├── mariadb/
│   └── scripts/
├── docs/
│   ├── architecture.md
│   ├── hardware.md
│   ├── database.md
│   ├── api.md
│   ├── security.md
│   ├── installation.md
│   ├── wifi.md
│   ├── permissions.md
│   ├── synchronization.md
│   ├── development.md
│   ├── releases/
│   └── private/
└── tests/
```

Não criar diretórios vazios apenas para aparentar arquitetura completa.

Ajuste a estrutura quando houver exigências do ESP-IDF, CMake ou das ferramentas de build.

Mantenha o código organizado e documentado.

---

# 28. VERSIONAMENTO GIT — OBRIGATÓRIO

Este projeto será desenvolvido em múltiplas versões.

Utilize Git com versionamento semântico.

Formato:

`MAJOR.MINOR.PATCH`

Exemplos:

- v0.1.0
- v0.2.0
- v0.3.0
- v1.0.0

## 28.1. Branches

A branch `main` deverá representar a última versão estável.

Cada etapa deverá ser implementada em uma branch exclusiva.

Padrão:

```text
release/v0.1.0-platform
release/v0.2.0-database
release/v0.3.0-authentication
release/v0.4.0-interface
release/v0.5.0-products
release/v0.6.0-customers
release/v0.7.0-sales
release/v0.8.0-inventory
release/v0.9.0-cash
release/v0.10.0-reports
release/v0.11.0-offline
release/v0.12.0-security
release/v1.0.0-stable
```

As versões intermediárias não precisam ser distribuídas como produto final, mas devem permanecer identificáveis.

## 28.2. Fluxo obrigatório por versão

Para cada etapa:

1. Verifique o estado do repositório.
2. Confirme que não existem alterações não relacionadas.
3. Atualize a base local conforme a estratégia do repositório.
4. Crie a nova branch de versão.
5. Implemente as funcionalidades previstas.
6. Execute testes.
7. Corrija erros.
8. Atualize documentação.
9. Atualize CHANGELOG.
10. Atualize VERSION.
11. Registre commits com mensagens descritivas.
12. Execute verificações de segurança e análise de segredos.
13. Faça push para a branch remota.
14. Apresente o hash do commit.
15. Registre os testes executados.
16. Prepare integração com `main`.

Não utilizar `git push --force` para sobrescrever histórico.

Não apagar branches de versões anteriores automaticamente.

Não reescrever versões já publicadas.

## 28.3. Integração à main

Uma versão aprovada deverá ser integrada à `main` seguindo as proteções e permissões do repositório.

Preferir Pull Requests quando disponíveis.

Se o repositório possuir regras de aprovação ou proteção, respeite-as.

Depois da integração, criar a tag correspondente à versão aprovada.

As novas branches devem partir da base estável atualizada.

Se não houver acesso ao repositório remoto ou permissão para push, informar claramente o impedimento e deixar os commits preparados localmente.

Nunca afirmar que realizou push sem confirmação do Git.

## 28.4. Commits

Utilizar Conventional Commits:

```text
feat: implement product registration
fix: prevent duplicate sale submission
refactor: separate database repository
docs: update docker installation
test: add inventory transaction tests
chore: prepare release v0.7.0
```

## 28.5. Documentação por versão

Criar um arquivo em `docs/releases/` contendo:

- Número da versão.
- Data.
- Branch.
- Commit.
- Funcionalidades adicionadas.
- Arquivos principais alterados.
- Alterações SQL.
- Migrações necessárias.
- Compatibilidade firmware/API.
- Resultado dos testes.
- Problemas conhecidos.
- Próximos passos.

Não alterar silenciosamente contratos de API ou formatos do armazenamento local.

---

# 29. PLANO DE DESENVOLVIMENTO POR ETAPAS

A implementação deverá seguir rigorosamente as etapas abaixo.

## VERSÃO 0.1.0 — PLATAFORMA TAB5

Objetivo: base funcional do firmware.

Implementar:

- ESP-IDF.
- Inicialização do display.
- LVGL.
- Teclado físico.
- Touchscreen.
- Menu básico.
- Identificação de hardware.
- Montagem do microSD.
- Logs.
- Tela de diagnóstico.

Critérios:

- Firmware compila.
- Interface inicia.
- Teclado funciona.
- Touch funciona.
- microSD é reconhecido.

Não avançar com erros de inicialização conhecidos sem documentar a causa.

## VERSÃO 0.2.0 — INFRAESTRUTURA E BANCO

Objetivo: servidor funcional.

Implementar:

- Docker Compose.
- MariaDB.
- API inicial.
- Caddy.
- HTTPS.
- Schema SQL inicial.
- Scripts de instalação.
- Migrações.
- Healthchecks.
- Backups.

Critérios:

- Containers inicializam.
- Banco persiste.
- Scripts SQL funcionam.
- API consulta o banco.
- HTTPS valida certificado.
- MariaDB não possui porta pública.
- Backup e restauração passam nos testes.

## VERSÃO 0.3.0 — ADMINISTRAÇÃO E AUTENTICAÇÃO

Implementar:

- Assistente de primeiro boot.
- Wi-Fi.
- Configuração da API.
- Administrador local.
- Geração de credenciais.
- Cadastro inicial do administrador remoto.
- Login.
- Tokens.
- Sessões.
- Perfis.
- Permissões.
- Logout.

Critérios:

- Configurações sobrevivem a reinício.
- Login funciona.
- Senhas são protegidas.
- Usuários sem permissão são bloqueados.
- Arquivos com credenciais não são publicados.

## VERSÃO 0.4.0 — INTERFACE PRINCIPAL

Implementar:

- Dashboard.
- Menus.
- Navegação.
- Temas.
- Componentes reutilizáveis.
- Mensagens.
- Formulários.
- Indicadores de rede.
- Indicadores de sincronização.

Critérios:

- Interface totalmente navegável.
- Nenhum travamento durante comunicação.
- Legibilidade adequada.
- Compatibilidade com teclado físico.

## VERSÃO 0.5.0 — PRODUTOS

Implementar:

- Cadastro.
- Edição.
- Consulta.
- Filtros.
- Categorias.
- Preços.
- Cache de produtos.

Critérios:

- CRUD funcional.
- Validação no backend.
- Permissões aplicadas.
- Dados persistentes.
- Consultas pelo cache funcionando.

## VERSÃO 0.6.0 — CLIENTES E FORNECEDORES

Implementar:

- Cadastros.
- Pesquisa.
- Edição.
- Histórico básico.
- Validação de documentos.
- Integração com permissões.

Critérios:

- Persistência correta.
- Pesquisa funcional.
- Dados pessoais protegidos.
- Clientes inativos preservados no histórico.

## VERSÃO 0.7.0 — VENDAS / PDV

Implementar:

- Carrinho.
- Quantidades.
- Descontos.
- Formas de pagamento.
- Finalização.
- Confirmação no servidor.
- Integridade transacional.
- Idempotência.
- Histórico de vendas.
- Cancelamento autorizado.

Critérios:

- Venda completa funciona.
- Estoque é atualizado.
- Operação falha sem gravação parcial.
- Reenvio não duplica venda.
- Permissões são verificadas.

## VERSÃO 0.8.0 — ESTOQUE

Implementar:

- Entradas.
- Saídas.
- Ajustes.
- Histórico.
- Saldo.
- Estoque mínimo.
- Controle concorrente.

Critérios:

- Saldos corretos.
- Movimentações auditadas.
- Sem estoque negativo não autorizado.
- Integridade em operações simultâneas.

## VERSÃO 0.9.0 — CAIXA E FINANCEIRO

Implementar:

- Abertura.
- Sangria.
- Suprimento.
- Fechamento.
- Recebimentos.
- Contas a receber.
- Contas a pagar.
- Categorias financeiras.

Critérios:

- Totais consistentes.
- Operações autorizadas.
- Fechamento correto.
- Histórico preservado.

## VERSÃO 0.10.0 — RELATÓRIOS

Implementar:

- Relatório de vendas.
- Relatório de produtos.
- Relatório de estoque.
- Relatório de caixa.
- Relatório por vendedor.
- Filtros por período.
- Consultas agregadas.

Critérios:

- Valores conferem com transações.
- Permissões são aplicadas.
- Consultas são paginadas.
- Desempenho aceitável.

## VERSÃO 0.11.0 — OFFLINE E SINCRONIZAÇÃO

Implementar:

- Cache persistente.
- Atualização incremental.
- Estado de sincronização.
- Rascunhos locais.
- Fila persistente de operações, quando segura.
- Detecção de conflitos.
- Retentativas.
- Idempotência.

Critérios:

- Desconexão não corrompe o cache.
- Reinício não perde operações persistidas.
- Reenvio não duplica vendas.
- Conflitos são detectados.
- Falhas não são silenciosamente ignoradas.

## VERSÃO 0.12.0 — SEGURANÇA E ESTABILIDADE

Implementar:

- Revisão de autenticação.
- Revisão de permissões.
- Revisão de TLS.
- Auditoria.
- Testes de concorrência.
- Testes de corrupção.
- Tratamento de erros.
- Revisão de dependências.
- Proteção adicional de segredos.
- Documentação de recuperação.

Critérios:

- Testes automatizados aprovados.
- Nenhum segredo publicado.
- Comportamento seguro diante de falhas.
- Integridade validada.
- Problemas críticos corrigidos.

## VERSÃO 1.0.0 — ESTÁVEL

Entregar:

- Firmware funcional.
- Backend funcional.
- Docker Compose validado.
- Banco estruturado.
- Migrações.
- Interface em português.
- Autenticação.
- Permissões.
- Cadastro de produtos.
- Cadastro de clientes.
- PDV.
- Estoque.
- Caixa.
- Relatórios.
- Cache.
- Configuração de Wi-Fi.
- Administrador local.
- Documentação completa.
- BIN de distribuição, quando viável.
- Tag v1.0.0.

Não declarar a versão estável antes de validar os requisitos obrigatórios.

---

# 30. TESTES AUTOMATIZADOS

Criar testes reais.

## Banco de dados

Testar:

- Criação de tabelas.
- Chaves estrangeiras.
- Constraints.
- Índices.
- Migrações.
- Backup.
- Restore.
- Concorrência.
- Rollback.

## Autenticação

Testar:

- Senha correta.
- Senha incorreta.
- Usuário inativo.
- Token expirado.
- Token revogado.
- Tentativas excessivas.
- Usuário sem permissão.
- Acesso administrativo.

## Vendas

Testar:

- Venda simples.
- Venda com vários itens.
- Desconto.
- Pagamento misto.
- Estoque insuficiente.
- Falha durante transação.
- Envio duplicado.
- Cancelamento.
- Devolução.

## Sincronização

Testar:

- Perda de conexão.
- Timeout.
- Reinício do dispositivo.
- Operações pendentes.
- Conflito de estoque.
- Conflito de preço.
- Duplicidade de envio.
- Resposta perdida após commit.

## Firmware

Testar:

- Inicialização.
- Teclado.
- Wi-Fi.
- HTTPS.
- microSD.
- Cache.
- Formulários.
- Navegação.
- Uso de memória.

Criar testes unitários executáveis fora do Tab5 para a lógica independente de hardware.

Não confundir compilação bem-sucedida com validação no dispositivo.

---

# 31. DESEMPENHO E RECURSOS

O Tab5 possui recursos limitados em comparação a computadores tradicionais.

O cliente não deverá processar relatórios complexos ou carregar todo o banco em memória.

A API deverá executar operações pesadas.

Implementar:

- Paginação.
- Cache.
- Limites de payload.
- Reutilização de conexões HTTPS quando adequada.
- Renderização eficiente.
- Uso racional da PSRAM.
- Alocações controladas.
- Processamento assíncrono de rede.
- Watchdog.
- Recuperação de falhas.

Objetivos iniciais, sujeitos a medição:

- Resposta visual imediata às teclas.
- Consultas locais rápidas.
- Ausência de congelamentos durante rede.
- Memória estável após navegação repetida.
- Inicialização previsível.
- Recuperação de conexão sem reiniciar o firmware.

Registrar medições reais em `docs/performance.md`.

---

# 32. SEGURANÇA, PRIVACIDADE E RECUPERAÇÃO

Adotar as boas práticas da LGPD e de segurança da informação.

Exigir:

- Coleta mínima de dados pessoais.
- Autorização em todas as operações protegidas.
- Senhas com hash seguro.
- TLS verificado.
- Credenciais fora do Git.
- Usuários SQL com privilégios mínimos.
- Logs sanitizados.
- Cache local minimizado.
- Política de expiração de sessões.
- Backups.
- Procedimento de restauração.
- Auditoria.
- Controle de acesso por perfis.

Documentar riscos residuais do armazenamento em microSD removível.

Avaliar mecanismos de criptografia do cache se houver dados pessoais armazenados.

Não utilizar o cartão microSD para guardar senhas administrativas em texto puro.

Não ativar irreversivelmente eFuses, Secure Boot ou Flash Encryption sem procedimento de implantação apropriado, documentação e estratégia de recuperação.

Durante o desenvolvimento, manter um perfil de configuração de testes separado do perfil de produção.

---

# 33. M5LAUNCHER E DISTRIBUIÇÃO

Investigar a compatibilidade do firmware com M5Launcher.

Produzir:

- BIN da aplicação.
- Instruções de compilação.
- Instruções de gravação por USB.
- Instruções de instalação via M5Launcher, quando suportado.
- Descrição de partições.
- Requisitos de armazenamento.
- Procedimento de atualização.

Não presumir que um BIN de aplicação convencional pode ser instalado pelo launcher sem ajustes.

Garantir que a atualização não apague desnecessariamente:

- Configuração Wi-Fi.
- Configuração da API.
- Identificador do dispositivo.
- Credenciais provisionadas.
- Dados persistentes.
- Arquivos do microSD.

Validar o comportamento de atualização e restauração.

---

# 34. CI/CD

Criar GitHub Actions para:

- Testes unitários do backend.
- Testes de integração com MariaDB.
- Análise estática.
- Validação SQL.
- Verificação de secrets.
- Build Docker.
- Build do firmware, quando o ambiente permitir.
- Geração de artefatos.
- Validação de versões.

Não colocar senhas reais no workflow.

Utilizar secrets do ambiente de CI quando necessário.

As falhas de testes devem impedir a classificação da versão como estável.

---

# 35. DOCUMENTAÇÃO OBRIGATÓRIA

Produza documentação que permita a outra pessoa instalar e manter o sistema sem conhecimento prévio do código.

Documentos:

1. `README.md` — visão geral.
2. `docs/architecture.md` — arquitetura.
3. `docs/hardware.md` — hardware e pinagem.
4. `docs/installation.md` — instalação completa.
5. `docs/database.md` — modelo e SQL.
6. `docs/api.md` — endpoints.
7. `docs/security.md` — segurança.
8. `docs/wifi.md` — configuração de rede.
9. `docs/permissions.md` — perfis e permissões.
10. `docs/synchronization.md` — cache e sincronização.
11. `docs/development.md` — ambiente de desenvolvimento.
12. `docs/performance.md` — medições.
13. `docs/releases/` — histórico das versões.
14. `docs/private/INITIAL_CREDENTIALS.md` — credenciais locais, não versionadas.

Todos os comandos apresentados na documentação devem corresponder aos arquivos efetivamente produzidos.

Não documentar funcionalidades inexistentes como se estivessem implementadas.

---

# 36. CRITÉRIOS DE ACEITAÇÃO FINAL

Considere o projeto concluído quando:

1. O Tab5 inicializar a aplicação.
2. A tela funcionar em paisagem.
3. O teclado físico controlar a interface.
4. O touchscreen funcionar.
5. O Wi-Fi puder ser configurado pelo usuário.
6. A API puder ser configurada localmente.
7. A conexão HTTPS validar o certificado.
8. O administrador local funcionar.
9. O login de usuários funcionar.
10. As permissões forem verificadas pelo servidor.
11. O Docker Compose inicializar os serviços.
12. O MariaDB possuir schema SQL funcional.
13. Os dados persistirem após reinicialização dos containers.
14. Produtos puderem ser cadastrados e consultados.
15. Clientes puderem ser cadastrados.
16. Vendas puderem ser realizadas.
17. Pagamentos puderem ser registrados.
18. O estoque for atualizado corretamente.
19. O caixa puder ser aberto e fechado.
20. Relatórios exibirem valores corretos.
21. O microSD armazenar cache local.
22. O sistema tratar interrupções de conexão.
23. Vendas não forem duplicadas por reenvio.
24. Testes de transação e rollback passarem.
25. Senhas não estiverem expostas no repositório.
26. Cada versão possuir branch remota identificável.
27. Tags e CHANGELOG estiverem consistentes.
28. A documentação de instalação estiver completa.
29. Os builds forem reproduzíveis.
30. As limitações conhecidas estiverem registradas.

---

# 37. INSTRUÇÕES FINAIS AO CODEX

Você deverá atuar como arquiteto de software, desenvolvedor embarcado, desenvolvedor backend, DBA e responsável pelo processo de versionamento.

Regras obrigatórias:

- Examine o repositório antes de modificar arquivos.
- Não substitua código funcional sem necessidade.
- Prefira bibliotecas estáveis e documentadas.
- Não invente APIs de hardware.
- Não use credenciais fixas.
- Não desabilite TLS para contornar erros.
- Não exponha o banco de dados diretamente à internet.
- Não envie senhas para o Git.
- Não implemente regras comerciais críticas somente no cliente.
- Não utilize FLOAT para dinheiro.
- Não apresente exemplos como implementação completa.
- Não deixe funções vazias como solução definitiva.
- Não declare testes executados quando não foram executados.
- Não avance deixando erros de build conhecidos sem registro.
- Não implemente todas as versões em um único commit.
- Não concentre todo o código em um único arquivo.
- Não realize mudanças não relacionadas em outros projetos.
- Não sobrescreva branches remotas.
- Preserve o histórico das versões.
- Utilize licença MIT para o código original, respeitando as licenças das dependências.

**Procedimento inicial obrigatório:**

1. Inspecione o repositório Git.
2. Identifique o estado atual e o remote.
3. Pesquise e valide as tecnologias.
4. Produza uma análise técnica de compatibilidade.
5. Defina as interfaces entre firmware, API e banco.
6. Crie o roteiro das versões.
7. Crie os documentos de arquitetura.
8. Inicie pela branch `release/v0.1.0-platform`.
9. Implemente a primeira etapa.
10. Execute os testes possíveis.
11. Documente o resultado.
12. Faça commit e push da branch, se houver acesso.
13. Apresente o resumo da versão e a próxima etapa.

As versões seguintes deverão seguir o plano estabelecido.

Ao concluir cada versão, informe:

- Versão.
- Branch.
- Commit.
- Funcionalidades implementadas.
- Testes executados e seus resultados.
- Arquivos alterados.
- Migrações SQL, quando houver.
- Resultado do push remoto.
- Limitações.
- Próximas atividades.

**Prioridade absoluta:** construir um ERP compacto, utilizável, confiável e seguro, preservando a consistência das vendas e do estoque.

O objetivo não é simplesmente exibir telas de cadastro, mas entregar um sistema funcional cuja arquitetura permita evoluir até um produto comercial completo.
