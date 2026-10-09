# Armazenamento e sincronização 0.11

Configurações no microSD em /sdcard/ERP/config/settings.enc, AES-256-GCM com chave
derivada do PIN; desbloquear após reinício. Tema também no microSD. Não usar NVS
para configurações/dados ERP. Atualização OTA preserva formatos e arquivos existentes.

Catálogo /ERP/cache/catalog-<hash API e dispositivo>.enc: registros AES-GCM,
nonce de snapshot, posição autenticada e footer com quantidade/SHA-256 dos registros.
Valida o arquivo completo antes de expor resultados; truncamento/ordem/mistura falham.
Cache inválido pode recuperar .bak íntegro, exibindo data/revisão do backup; não o
apresenta como sincronização recente. Grava novo .tmp com flush/fsync, valida e renomeia.
Arquivo .delta temporário também é criptografado. Atualização interrompida preserva base.
Limite de 10.000 produtos; até oito resultados por página, incluindo busca offline PDV.
Cache .jsonl legado só é removido após concluir um novo catálogo criptografado da mesma API.

GET /api/v1/sync/products: revisão global, epoch do banco e sync_revision por produto.
As mutações de cadastro, categoria, estoque, venda e cancelamento atualizam a revisão
na mesma transação. Recebe somente diferenças desde a base; inativos também chegam.
Mescla em ordem por ID no microSD sem carregar o catálogo inteiro na RAM. Revisão mudou
entre páginas? Recusa 409, descarta temporário e mantém base. Tente Atualizar novamente.
Epoch diferente ou revisão do servidor menor? Reinicia download completo.
Restauração de banco deve renovar epoch antes de voltar a atender: ver release 0.11.
Não depender do relógio do Tab5 para determinar alterações. Datas apenas informam idade.

/ERP/offline/profile-0.enc: último perfil online confirmado, sem tokens ou senhas ERP.
Desbloqueio local e Abrir offline permitem somente produtos/rascunhos. Não equivalem
a uma sessão ERP autenticada; permissões remotas podem mudar. Para enviar, fazer login
novamente e validar RBAC na API. Relatórios, documentos de clientes, caixa e estoque
não são persistidos nesse perfil/cache. Contatos continuam só em RAM.

/ERP/offline/draft-<operador>.enc: um rascunho criptografado por operador, vinculado
à API, dispositivo e chave do PIN. Salvar é explícito; não prometer persistência de
campos ainda não salvos. Abrir/carregar não envia operação. Preços/versões do cache
são provisórios: ao reconectar, Atualizar preços e Revisar e cobrar antes de confirmar.
Antes de concluir, o rascunho recebe a requisição com a chave original de idempotência.
Reinício antes do journal recupera essa requisição; pendência impede nova venda.
Confirmada pela API: limpa o rascunho vinculado e só então o journal. Limpeza falhou?
Mantém pendência. Tentativa abandonada: remove vínculo e preserva rascunho para revisão.
Rascunho corrompido bloqueia novo envio; não sobrescrever automaticamente.

Pendências protegidas no microSD ANTES de enviar, formatos anteriores preservados:
/ERP/pdv/pending.enc (vendas), /ERP/inventory/pending.enc (estoque),
/ERP/finance/pending.enc (caixa/categorias/contas/baixas).
Vínculo PIN, operador, terminal e URL API; sem tokens ou senhas no pedido.
Fila serial limitada a uma tentativa em cada módulo; capacidade segura atual.
Reenviar é explícito e preserva corpo/chave; não envia lote financeiro em segundo plano.
Resolver confirma resultado ou encerra chave na API, impedindo envio tardio.
Só limpar após confirmação; falha/corrupção/escopo incompatível preserva arquivo e
bloqueia novos envios do módulo. Expiração da sessão exige login; não reutilizar perfil
local para autenticar a fila. Conflitos de preço/estoque/permissão não sobrescrevem MariaDB.

Pendências não impedem desbloquear/logar para recuperá-las. Pendências/rascunhos impedem
alterar PIN, URL API e restaurar configuração; excluir rascunhos dos operadores primeiro.
Rede Wi-Fi pode ser reconfigurada. Fechar caixa exige resolver vendas/estoque pendentes.
Estado definitivo no MariaDB. Sem SD gravável, não enviar operação que exija registro.
FATFS não garante atomicidade absoluta após perda física de energia; flush, cópia
anterior e validação detectam inconsistências, sem formatar cartão ou apagar pendências.
