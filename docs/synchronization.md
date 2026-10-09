# Armazenamento e sincronização

Configurações no microSD em /sdcard/ERP/config/settings.enc, AES-256-GCM com chave
derivada do PIN; desbloquear após reinício. Tema também no microSD. Não usar NVS
para configurações/dados ERP. Atualização OTA preserva formatos e arquivos existentes.
Cache paginado de produtos suporta consultas; contatos são mantidos apenas em RAM.

Pendências protegidas no microSD ANTES de enviar:
/ERP/pdv/pending.enc (vendas), /ERP/inventory/pending.enc (estoque),
/ERP/finance/pending.enc (caixa/categorias/contas/baixas).
Vínculo PIN, operador, terminal e URL API; sem tokens ou senhas no pedido.
Uma tentativa por módulo. Reenvio preserva corpo/chave. Resolver confirma o resultado
ou encerra a chave na API, impedindo envio tardio. Só limpar após confirmação;
falha/corrupção/escopo incompatível preserva arquivo e bloqueia novos envios do módulo.

Pendências não impedem desbloquear/logar para recuperá-las. Impedem trocar PIN,
URL API e restaurar configurações; rede Wi-Fi pode ser reconfigurada. Fechar caixa
no Tab5 exige resolver pendências de vendas/estoque. Estado definitivo no MariaDB.

Operações comerciais ainda exigem conexão e confirmação da API; não existe venda
financeira definitiva offline. Offline/incremental e filas avançadas pertencem à
0.11, com testes de corrupção, conflitos e recuperação. FATFS não garante atomicidade
absoluta após perda de energia; arquivos contam com gravação protegida e backup.
Sem cartão gravável, não enviar operação que exija registro persistente.
