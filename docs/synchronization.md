# Armazenamento e sincronização

v0.1.0 monta SDMMC/FATFS, testa escrita em /sdcard/ERP e registra log limitado em
/ERP/logs/platform.log. Não existem cache SQL/JSON ou fila comercial nesta etapa.
Não criar banco vazio só para aparentar funcionalidade.

Planejado: cache de catálogo incremental com cursor servidor; indicar dados antigos.
Fila segura somente depois de testes de falha: UUID, idempotência, usuário/dispositivo,
estado, tentativas, último erro. Persistir antes de enviar e não perder rejeitados.
Revalidar sessão/RBAC/preço/estoque/caixa no servidor. Não sobrescrever conflitos.
Offline inicial permite consultas/rascunhos; não confirma venda definitiva.

Sem SD: menu continua; operação que exigir fila persistente será desabilitada.
Nenhuma venda financeira pendente ficará exclusivamente em RAM. FATFS não promete
atomicidade absoluta após queda de energia. Corrupção, espaço cheio, remoção e
recuperação serão testados na v0.11.0 antes de habilitar operações pendentes.
