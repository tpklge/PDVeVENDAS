# Segurança e estabilidade — 0.12.0

Acesso comercial exige sessão ERP e RBAC no servidor. PIN local de quatro números
continua desbloqueando somente o microSD; não recebe permissões da API. Senha ERP
mantém mínimo de oito caracteres, sem novas exigências de composição. Não há senha
universal nem mudança de credenciais nesta atualização.

## Autenticação e autorização

Argon2id no servidor (64 MiB, três iterações, duas lanes). Tokens aleatórios são
armazenados apenas por SHA-256 no banco e em RAM no terminal. Access expira em
15 minutos; família de refresh tem limite absoluto de oito horas. Refresh é
rotacionado; replay revoga a família. Usuário inativo é recusado imediatamente.
Mudança/redefinição de senha revoga todas as sessões. Login, refresh, logout,
alteração de senha e CLI usam ordem de bloqueio usuário → sessão, impedindo
renovação depois de revogação concorrente. Não manter bloqueio aguardando senha
no teclado da CLI.

Cinco falhas em 15 minutos bloqueiam o usuário por esse intervalo, com resposta
igual para usuário desconhecido/inativo/senha incorreta. O limite é por nome de
usuário; não é um limitador global distribuído de tráfego. Evitar expor a API em
outros entrypoints além do HTTPS configurado. Não impor novas regras ao PIN.
Permissões são lidas da base a cada pedido; alterações de papéis já afetam tokens
emitidos. Login inicial não libera operações antes de trocar a senha.

Login negado/limitado e replay de refresh geram auditoria com correlação, sem senha
ou token. Nome fornecido em login negado fica somente como hash. Eventos comerciais
bem-sucedidos são auditados na mesma transação dos dados. Falhas inesperadas logam
apenas classe e correlação; não imprimem SQL, parâmetros, corpos nem traceback.
Validação HTTP não devolve valores digitados. SQL usa parâmetros/ORM.

## Rede e dependências

TLS exige CA/bundle, hostname e horário; redirecionamento automático é recusado.
Firmware recusa API que não use HTTPS e builds com validação TLS insegura. Traefik
mantém Let's Encrypt, entrypoint websecure, rede meshcentral_proxy e resolver
letsencrypt. HSTS max-age=31536000 somente no domínio da API; não afeta subdomínios.
API interna mantém HTTP isolado atrás do proxy, sem porta publicada; não confiar em
X-Forwarded-* recebido do cliente. Cabeçalhos no-store, nosniff e correlação em
respostas da aplicação. Corpo máximo 64 KiB antes do parsing, inclusive chunked.

ESP-IDF permanece 5.4.4, BSP/CPU/LVGL/conexão preservados. A biblioteca criptográfica
usa o fork oficial Espressif Mbed TLS **3.6.7**, commit
`2b96dd8eebe880f304c69976b3c2fa0c5100cbb6`. A preparação copia a integração do SDK
para build/security e baixa o arquivo fixado com SHA-256; SDK compartilhado não é
modificado. Corrige, entre outros, [falha de cálculo EMS CVE-2026-50581](https://mbed-tls.readthedocs.io/en/latest/security-advisories/mbedtls-security-advisory-2026-07-extended-master-secret-calculation-failure-ignored/).
Ver [avisos oficiais](https://mbed-tls.readthedocs.io/en/latest/security-advisories/),
[fork do fornecedor](https://github.com/espressif/mbedtls/tree/2b96dd8eebe880f304c69976b3c2fa0c5100cbb6)
e [licença](licenses/mbedtls.txt), escolhida sob Apache-2.0. DTLS, TLS 1.3 e EC J-PAKE
não são habilitados no firmware atual; testes TLS nativos forçam a mesma versão 1.2.

23 pacotes Python fixados com hashes dos artefatos; Docker usa --require-hashes.
`python3 tools/audit_dependencies.py` consulta avisos ativos e hashes na API primária
PyPI e falha se serviço indisponível, aviso ativo ou hash divergente. Em 09/10/2026,
nenhum aviso ativo retornado para as versões fixadas. Isso é uma consulta datada,
não garantia contra falhas ainda desconhecidas. Imagens base/digests e componentes
ESP do dependencies.lock mantidos; atualização exige novo build e testes nas duas
arquiteturas. Repetir revisão antes de publicar futuras versões.

## Segredos, cartão e falhas

API sem root, somente leitura, cap_drop ALL, no-new-privileges, logs limitados.
SQL interno, usuários distintos de app/migração/root e secrets por serviço.
Backups com modo 0600 e diretório restrito; guardar cópia criptografada fora do host
é responsabilidade operacional. Scanner bloqueia caminhos privados, .env reais,
chaves privadas e padrões de tokens/credenciais. Não identifica toda senha possível;
não publicar cartão, backup nem relatório docs/private.

Configuração, Wi-Fi, perfil offline, catálogo e rascunhos: AES-256-GCM no microSD;
PBKDF2-HMAC-SHA256 200.000 iterações, sem NVS ERP, senha/chave local não persistidas.
PIN curto por escolha do usuário mantém menor resistência a adivinhação de uma cópia
roubada do cartão. Nada nesta release muda o PIN ou a conexão.

Pendências financeiras mantêm envelope v1, chave, contexto, operador/API/dispositivo
e pedido original. Limpar exige leitura/autenticação/contexto corretos; erro não
apaga a pendência. Arquivo existente corrompido não recupera backup antigo de forma
silenciosa. Arquivo principal ausente após rename recupera .bak completo. Falha de
acesso ao journal impede trocar PIN/API/reset. Buffers são zerados antes de liberar;
falha de alocação recusa operação e preserva arquivos. Cache completo possui footer
SHA-256/contagem e vínculo de snapshot/posição. FATFS não garante atomicidade física
absoluta; ver [recuperação](recovery.md).

Falha transacional reverte estoque, venda, pagamentos e auditoria; erro 500/503 não
prova se um resultado de outra conexão já confirmou. Continuar usando a chave
persistida e Resolver; não gerar pedido substituto. Página de relatório também
inclui epoch, impedindo continuar leitura de uma história restaurada.

## Evidência e limites

Testes API percorrem todas as operações comerciais sem autenticação, removem
permissões de sessão ativa, inativam usuário, testam deadlines, auditoria, limites,
erros e rollback com falha de escrita. CI MariaDB real em AMD64/ARM64 exercita
concorrência de estoque/caixa/idempotência e revogação com reset segurando bloqueio.
Código real do armazenamento roda contra a mesma criptografia: corrupção/truncamento,
chave/contexto/operador, reset, escrita interrompida e falta de memória sem vazamento.
Handshakes TLS nativos recusam CA desconhecida, hostname errado e certificado
expirado; só enviam bytes de aplicação depois da validação.

Não afirmar retirada física de energia, corrupção física de cartão, oito horas de
uso ou 1.000 trocas de tela sem medições no dispositivo. Não gravar eFuses ou exigir
Secure Boot/Flash Encryption irreversível para esta entrega. Versão 1.0 só será
marcada após validação final no servidor/Tab5, conforme o roteiro.
