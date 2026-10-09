# Homologação antes de 1.0

A etapa 0.11 foi aprovada pelo usuário em 09/10/2026. A 0.12 é a revisão final,
com implementação entregue e confirmação no dispositivo/OCI ainda necessária.
Não substituir confirmação física por testes nativos ou build.

| Critérios finais da especificação | Evidência atual | Fechamento |
|---|---|---|
| 1–4: boot, paisagem, teclado, touch | Plataforma e uso dos módulos aprovados pelo usuário | Repetir boot/navegação com OTA 0.12 |
| 5–9: Wi-Fi/API, HTTPS, PIN e login | Conexão e sessão ERP aprovadas nas etapas anteriores; HTTPS OCI válido | Novo TLS 3.6.7 precisa conectar no Tab5 |
| 10: permissões | 68 testes API, todas as rotas comerciais sem token, alteração de papéis e usuário inativo | CI da release aprovado |
| 11–13: Compose, schema e persistência | OCI confirmado; MariaDB nativo AMD64/ARM64 e restore isolado | validate-security.sh no OCI após atualização |
| 14–20: produtos, clientes, vendas, pagamentos, estoque, caixa, relatórios | Etapas 0.5–0.10 aprovadas pelo usuário; testes transacionais/concorrentes | Uma venda/caixa com OTA/API 0.12 |
| 21–23: cache, interrupções e idempotência | Rascunho reiniciado explicitamente confirmado; aprovação geral 0.11; replay/conflitos no CI | Conferir rascunho após novo OTA |
| 24–25: rollback e segredos | Falhas injetadas revertem pagamentos/estoque/auditoria; scanners/hashes sem credenciais publicadas | CI final aprovado |
| 26–27: branches e tags/CHANGELOG | Branches remotas 0.1–0.12; CHANGELOG coerente; nenhuma tag 1.0 criada | Branch/tag 1.0 só após homologação |
| 28–30: instalação, builds e limitações | installation/security/recovery atualizados; imagens/pacotes/SDK/componentes fixados; build local e CI | Reunir resultados e artefatos da estável |

Registre a saída de validate-security.sh, versão/hash do BIN e resultado do uso
no Tab5. Esses registros podem vir da confirmação do usuário; não solicitar senhas
nem copiar documentos/backup para o chat.

Medições de boot, heap sob navegação, latência, oito horas e falha física do cartão
não foram realizadas nesta sessão. Permanecem como ensaios de operação em
performance.md. Testes de corrupção automatizados usam arquivos temporários e a
biblioteca real, sem alterar o cartão do usuário. Builds são refeitos com versões
fixadas; timestamps e diferenças de host podem alterar o hash, e não foi comprovada
igualdade bit a bit entre hosts.

Limitações funcionais mantidas: PDV/comprovante não fiscal, pagamentos declarados
sem confirmação de adquirente, cancelamento integral com reversão de estoque/caixa,
sem devolução parcial/reembolso externo automático; rascunhos offline sem reserva
ou venda definitiva offline. Configuração obrigatória no microSD por escolha do
usuário; sem cartão não existe configuração para login nem fila financeira segura.
PIN curto aprovado pelo usuário; guardar cartão e backups em local protegido.

Após os resultados finais, criar release/v1.0.0-stable, atualizar versões/notas,
compilar/testar os artefatos e somente então publicar tag estável. Não alterar dados
comerciais nem provisionar novamente a instalação existente.
