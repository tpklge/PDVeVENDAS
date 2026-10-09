# Histórico

## 0.11.0 — offline e sincronização implementados; validação física pendente

- Catálogo incremental por revisão/epoch, incluindo preços, estoque e inativação.
- Cache AES-GCM no microSD, registros vinculados ao snapshot/posição e footer SHA-256.
- Último perfil offline limitado a produtos e rascunhos; sem persistir tokens/senha ERP.
- Salvar/carregar/excluir rascunho por operador, API, dispositivo e PIN.
- Rascunho vinculado à mesma tentativa durante finalização, sem recriar venda após reinício.
- Journals existentes preservados; fila serial por módulo e retentativas explícitas.
- Migração aditiva 008_offline; backup, dados e credenciais preservados.
- 49 testes de API; testes reais de criptografia, corrupção, vínculo e recuperação.
- CI MariaDB AMD64/ARM64, backup/restore, firmware e armazenamento aprovados (1fc24de).

## 0.10.0 — relatórios validados pelo usuário

- Doze relatórios nativos, filtros por período/IDs, totais SQL e paginação por revisão.
- Fuso Cuiabá, dinheiro líquido de troco, cancelamentos e rateio exato de descontos.
- Estoque por unidade, histórico, caixa fechado imutável e contas por vencimento.
- RBAC adicional para valores financeiros; nenhum documento pessoal em relatórios.
- Migração 007_reports acrescenta apenas índices; atualização com backup.
- 45 testes API e build ESP32-P4 aprovados localmente.
- CI MariaDB AMD64/ARM64, relatórios, backup/restore e firmware aprovados (417a455).

## 0.9.0 — fluxo básico de caixa validado no Tab5

- Usuário confirmou abertura de caixa, duas vendas e encerramento em 09/10/2026.
- Usuário percebeu desbloqueio mais rápido; tempo não medido.
- Desbloqueio: pausas por tempo, mantendo PBKDF2 200.000 e arquivos existentes.
- Wi-Fi e verificações da API preservados; desbloqueio permite recuperar pendências.
- Abertura por operador/terminal, sangria, suprimento, fechamento e histórico.
- Vendas integram caixa, pagamentos mistos e troco; fechamento imutável e auditado.
- Categorias, contas a pagar/receber, baixas parciais e filtros por vencimento.
- Recuperação financeira criptografada no microSD e barreira contra envio tardio.
- Migração aditiva 006_cash; backup antes de atualizar, sem alterar credenciais.
- Usuário aprovou os testes de estoque 0.8.0.
- 39 testes de API; MariaDB AMD64/ARM64, concorrência e backup aprovados no CI.
- Build ESP32-P4 e testes portáteis aprovados localmente e no CI.

## 0.8.0 — estoque validado no Tab5

- API de saldo, estoque mínimo e histórico de movimentos.
- Entradas, saídas e ajustes justificados, com versão e idempotência.
- Movimentos, saldo e auditoria transacionais; bloqueios compartilhados com vendas.
- Tela nativa, pesquisa/filtros, revisão e confirmação de movimento.
- Recuperação criptografada no microSD; resolução impede envio atrasado.
- Histórico completo e integração com vendas/cancelamentos.
- 33 testes locais da API aprovados; atualização preserva dados existentes.
- Usuário confirmou o fechamento 0.7.1 funcionando.

## 0.7.1 — fechamento de venda mais claro

- Revisar e cobrar → Confirmar pagamento e concluir → Venda concluída.
- Botão de confirmação ampliado para manter a legenda inteira visível.
- Usuário confirmou vendas funcionando na etapa 0.7.0.

## 0.7.0 — vendas / PDV implementada; validação física pendente

- Carrinho, descontos autorizados, pagamentos mistos e troco em dinheiro.
- Venda/estoque/pagamentos transacionais; repetição com chave idempotente.
- Recuperação criptografada no microSD e resolução contra envio atrasado.
- Histórico, compras por cliente e cancelamento comercial integral auditado.
- Migração incremental preserva dados e registra saldo inicial de estoque.
- 27 testes da API e concorrência/backup em MariaDB AMD64/ARM64 aprovados.

## 0.6.0 — clientes e fornecedores validada

- Cadastros online, pesquisa paginada, edição, status e histórico de alterações.
- CPF/CNPJ opcionais, validação numérica/alfanumérica e permissões documentais.
- Dados pessoais apenas em RAM no Tab5; nenhum cache de contatos no microSD.
- Vínculos de fornecedores com produtos; migração incremental preserva dados.
- Mensagens identificam CPF/CNPJ e CEP inválidos; 21 testes de API aprovados.
- Usuário confirmou cadastro, pesquisa, edição, inativação e reativação em ambos os módulos.
- Etapa 0.5 validada fisicamente pelo usuário.

## 0.5.0 — produtos validada

- Cadastro, edição, filtros, categorias, preços e inativação na API e Tab5.
- Migração incremental, preços decimais, GTIN e concorrência por versão.
- Cache paginado no microSD, consultas sem rede e gravação apenas na API.
- Pool LVGL e buffers de tela na PSRAM: corrige travamento no boot e falta de DMA após Wi-Fi.
- Usuário validou cadastro, consulta, reinício, edição, desativação/reativação e filtros em 08/10/2026.
- Etapa 0.4 validada fisicamente pelo usuário.

## 0.4.0 — interface principal (candidata)

- Dashboard, menus, navegação por toque/teclado e sessão integrada.
- Temas claro/escuro persistidos no microSD e indicadores Wi-Fi/API.
- Módulos comerciais sinalizados como indisponíveis; sem dados fictícios.
- Etapa 0.3 validada no dispositivo: login, PIN e persistência microSD.

## 0.3.2 — senha ERP simplificada (candidata)

- ERP aceita 8 caracteres, sem requisitos de composição.
- Troca pelo terminal, sem eco, revoga sessões e dispensa repetir a senha inicial.
- Firmware informa falhas de sessão, validação e conexão na troca de senha.

## 0.3.1 — Wi-Fi, interface e microSD (candidata)

- Autoteste de boot mais rápido; criptografia das configurações preservada.
- Mensagem imediata, placeholders ocultos, legendas centralizadas e tema claro.
- Senha local mínima de 4 caracteres; requisito ERP permanece em 20.
- Configurações criptografadas no microSD, sem NVS, com cópia de recuperação.
- Rádio remoto selecionado como ESP32-C6: corrige assert e reinício na pesquisa Wi-Fi.

## 0.3.0 — administração e autenticação (candidata)

- Primeiro boot, admin-local e configurações criptografadas AES-GCM/PBKDF2.
- Wi-Fi remoto C6, pesquisa/seleção de redes, NTP e HTTPS verificado.
- Login ERP, troca obrigatória, sessões, perfis/permissões, refresh e logout.
- Troca local, bloqueio, confirmações de recuperação e diagnóstico preservado.
- Registro privado de credencial de dispositivo; sem segredo no firmware/Git.
- Aprovação depende da validação física no Tab5.

## 0.2.0 — infraestrutura aprovada

- MariaDB, SQL inicial, migrações, API e Traefik existente implantados no OCI.
- HTTPS validado pelo usuário com certificado Let's Encrypt e health ready.
- Secrets de arquivo, healthchecks, backup e restauração.
- Verificação de persistência e restauração isolada; CI Docker AMD64/ARM64.
- Validação final no OCI aprovada: persistência, backup restaurado e HTTPS.
- Firmware permanece em 0.1.1.

## 0.1.1 — fonte pt-BR

- Corrige glifos ausentes nas fontes: Latin-1 para ç/acentos nos tamanhos 20 e 28.
- Tema e widgets usam fonte pt-BR; símbolos LVGL mantidos por fallback.
- Linha de conferência de acentos na tela de entrada.
- Instalação e três telas testadas pelo usuário; revisão visual desta correção pendente.

## 0.1.0 — plataforma (candidata; validação física pendente)

- Projeto ESP-IDF 5.4.4 para ESP32-P4 e BSP oficial fixado.
- LVGL em paisagem, menu, diagnóstico e teste de entrada.
- Driver original Tab5 Keyboard em HID, I²C e interrupção GPIO50.
- microSD sem formatação automática; teste de escrita e log limitado.
- Núcleo C++ independente do hardware, documentação e CI da plataforma.
- Preparação de backend isolada da sequência de releases.
