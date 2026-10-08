# Preparação da etapa v0.2.0 — OCI

Base: firmware v0.1.1 com fontes pt-BR. A implantação do servidor é uma etapa
independente; este documento não declara a infraestrutura pronta.

Informações fornecidas pelo usuário em 08/10/2026:

- Servidor OCI Ampere, arquitetura ARM64.
- Ubuntu, kernel 6.17; versão possivelmente 24.04, ainda não confirmada.
- Docker será executado no servidor na nuvem; Traefik já instalado.
- Servidor: ampere.diadiatech.com.br.
- URL da API: https://tab5api.ampere.diadiatech.com.br.
- Rede externa compartilhada com Traefik: meshcentral_proxy.
- Resolver ACME informado: letsecnrypt (grafia preservada).
- Entrypoint HTTPS definido: websecure.
- Repositório: https://github.com/tpklge/PDVeVENDAS.

O kernel não identifica a versão do Ubuntu. Na sessão SSH do servidor, conferir:

```sh
cat /etc/os-release
uname -m
uname -r
df -h /
free -h
```

Esperado para arquitetura: `aarch64`. Registrar a versão do sistema antes de
selecionar o repositório de instalação do Docker, caso necessário. Ainda falta
um acesso SSH disponível para
executar e validar a implantação real. Ver [integração Traefik](traefik.md).
Não registrar senhas, chaves privadas ou tokens no repositório.

A entrega desta etapa deve incluir Compose, MariaDB, API inicial, Traefik/HTTPS,
schema inicial, migrações, healthchecks e scripts de instalação/backup/restauração.
Usar imagens compatíveis com ARM64 e versões fixadas. O Traefik atende 80/443;
manter o banco e a API na rede interna, com banco em volume persistente.

Aprovação exige testes reais de inicialização, persistência, consulta da API,
certificado HTTPS, ausência de porta pública do banco e backup/restauração.
Nenhum desses testes de servidor foi executado nesta preparação.

A implementação de backend previamente preparada continua preservada na branch
local `work/backend-preparation`; a integração ocorrerá conforme o escopo 0.2.0,
sem antecipar o módulo de autenticação da etapa 0.3.0.
