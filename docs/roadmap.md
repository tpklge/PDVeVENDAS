# Roteiro obrigatório

| Versão | Branch | Entrega / condição de aprovação |
|---|---|---|
| 0.1.0 | release/v0.1.0-platform | BSP/LVGL/teclado/touch/SD; compilar e testar na placa |
| 0.2.0 | release/v0.2.0-database | MariaDB/API/Caddy na OCI ARM64; TLS e backup/restore reais |
| 0.3.0 | release/v0.3.0-authentication | Primeiro boot, Wi-Fi, admin-local, login/RBAC; credenciais protegidas |
| 0.4.0 | release/v0.4.0-interface | Dashboard, temas, navegação e formulários sem bloqueio de rede |
| 0.5.0 | release/v0.5.0-products | Produtos, preços/categorias, consultas e cache paginado |
| 0.6.0 | release/v0.6.0-customers | Clientes/fornecedores, documentos e proteção de dados |
| 0.7.0 | release/v0.7.0-sales | PDV transacional, idempotência, estoque, pagamentos e cancelamento |
| 0.8.0 | release/v0.8.0-inventory | Movimentos, ajustes, mínimos e testes concorrentes |
| 0.9.0 | release/v0.9.0-cash | Caixa/financeiro, sangria/suprimento, fechamento e histórico |
| 0.10.0 | release/v0.10.0-reports | Relatórios agregados/paginados com autorização |
| 0.11.0 | release/v0.11.0-offline | Cache incremental, filas persistentes e resolução de conflitos |
| 0.12.0 | release/v0.12.0-security | Concorrência, corrupção, recuperação e revisão de segurança |
| 1.0.0 | release/v1.0.0-stable | Todos os critérios finais da especificação aprovados |

Não avançar com falhas de inicialização sem causa documentada. `main` será a base
aprovada; nenhuma tag estável antes da validação. Cada release terá testes,
CHANGELOG, VERSION, relatório, commit e push verificável. Não usar force push.
A preparação antecipada de backend não muda esta ordem e não será mesclada
antes da etapa correspondente.
