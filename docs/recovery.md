# Recuperação de configuração e dados

## microSD

Todos os arquivos ERP ficam em `/ERP` no cartão. Configuração em config/settings.enc;
catálogo em cache/catalog-<escopo>.enc; perfil/rascunhos em offline; pendências em
pdv/pending.enc, inventory/pending.enc e finance/pending.enc. Não há dados ERP na NVS.
Antes de trocar cartão, apagar firmware ou redefinir a instalação, desligue a
aplicação pelo launcher e copie **a pasta ERP inteira**, incluindo .bak/.tmp, para
armazenamento protegido. Guarde o PIN separadamente. Não retirar cartão com app ativo.
Uma troca de OTA preserva esses arquivos. O launcher não faz backup automático.

Configuração criptografada requer o PIN usado na gravação; backup não permite
recuperar PIN esquecido. Device ID/API/operador devem corresponder para pendências.
Cópia de cartão em outra placa não autoriza reenviar pedidos protegidos.
Trocar PIN/API/reset permanece bloqueado enquanto houver pendências/rascunhos.

Se cache corromper, Atualizar cache online pode reconstruí-lo ou usar backup íntegro.
O snapshot danificado é preservado quando recuperado. Cache não é banco comercial.
Se configuração ou journal corromper: pare, copie ERP inteira e preserve ambos os
arquivos. Não substitua um journal existente por .bak antigo nem toque Excluir para
tentar desfazer uma venda. Corrupção é bloqueada, não tratada como ausência.

Uma tentativa desconhecida deve ser reenviada/resolvida com a **mesma chave** pelo
operador, dispositivo e API originais. Após reconectar/login, o módulo recupera a
pendência e Resolver consulta o resultado ou encerra a chave antes de novo pedido.
Se o arquivo não puder ser decifrado, confirme o resultado e bloqueie a chave no
servidor antes de qualquer intervenção manual no cartão. Preserve a cópia para
inspeção; não invente uma venda substituta. Dado confirmado está no MariaDB.

## Servidor e restauração

Atualização normal: executar o script da release, que faz backup antes do build e
migrações. Não executar initialize/provision-admin, reimportar schema.sql, apagar
volumes ou credenciais. `docker/scripts/backup.sh` gera SQL comprimido com acesso
restrito. `validate-release.sh` verifica restauração em instância **isolada**, além
de persistência e HTTPS; não restaura sobre produção durante teste.

Para restaurar produção, na raiz `/home/ubuntu/TAB5_ERP`:

1. Pare a API: `docker compose --env-file docker/.env -f docker/compose.yaml stop api`.
2. Preserve um backup atual e confira a integridade do arquivo escolhido (`gzip -t`).
3. Leia `docker/scripts/restore.sh`: seu destino e parâmetros exigem confirmação
   explícita de restauração. Restaure somente o backup autorizado para essa base.
4. Com API parada, execute as migrações:
   `docker compose --env-file docker/.env -f docker/compose.yaml run --rm --no-deps -T migrate`.
5. Rode `bash docker/scripts/invalidate-sync.sh` antes de reativar a API. Renova epoch
   sem mudar dados comerciais; catálogo e páginas de relatório antigas são recusados.
6. Suba/verifique: `docker compose --env-file docker/.env -f docker/compose.yaml up -d --no-deps --wait api`
   e `curl --fail https://tab5api.ampere.diadiatech.com.br/health/ready`.
7. No Tab5, autentique novamente, atualize o cache/preços e confira rascunhos e
   pendências. Uma restauração pode retirar vendas feitas depois do backup; concilie
   resultados com comprovantes/caixa antes de decidir reenviar. Não automatizar essa decisão.

Falha de build não para a API atual. Falha de migração mantém API parada para evitar
uso de schema incompatível; preserve logs sem segredos, volume e backup. Corrija a
causa e repita a migração/up; não apagar base para tentar novamente. 0.12 mantém
schema 008_offline e arquivos v1 existentes.

Redefinir somente senha ERP: `docker compose --env-file docker/.env -f docker/compose.yaml exec api python -m app.cli reset-password --username admin`.
A senha é digitada sem eco (mínimo oito caracteres); todas as sessões são revogadas.
Isso não troca PIN, não altera vendas e não imprime credenciais.
