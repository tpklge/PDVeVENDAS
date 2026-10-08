# Integração com Traefik existente

URL escolhida: https://tab5api.ampere.diadiatech.com.br.
Servidor informado: ampere.diadiatech.com.br, OCI Ampere ARM64.

O Traefik já instalado será o proxy HTTPS da API. Ele mantém seu próprio resolver
ACME e armazenamento persistente de certificados. A implantação ERP não inicia
outro Traefik/Caddy e não precisa copiar certificados para o container da API.

`docker/compose.traefik.yaml` contém as labels e a rede externa compartilhada.
É um complemento, não uma implantação completa: o Compose base com API/MariaDB
ainda será integrado na etapa 0.2.0. O serviço API deverá escutar em 8000, sem
publicar essa porta no host. O MariaDB participa somente da rede backend interna.
O Traefik precisa ter o provider Docker habilitado e acesso à rede compartilhada.
Este modelo é para Docker Compose; uma instalação Swarm exige adaptação ao
provider Swarm e às labels de serviço.

Rede externa confirmada pelo usuário: `meshcentral_proxy` (Portainer).
Resolver informado pelo usuário no valor da label
`traefik.http.routers.traefik-dashboard.tls.certresolver`: `letsecnrypt`.
Preservar essa grafia, pois o identificador deve coincidir com a configuração
existente do Traefik.
Preencher a variável vazia `TRAEFIK_HTTPS_ENTRYPOINT` de
`docker/.env.traefik.example` com o nome real do entrypoint HTTPS. Não é necessário
alterar o Traefik para acrescentar um resolver se já houver um configurado.

Criar o registro DNS de `tab5api.ampere.diadiatech.com.br` apontando ao endereço
público atendido pelo Traefik. O DNS desse subdomínio deve resolver explicitamente
ou ser coberto por wildcard. Conferir também IPv6 se houver registro AAAA.

Um certificado wildcard de `*.ampere.diadiatech.com.br` pode cobrir esta API;
`*.diadiatech.com.br` não cobre esse nível adicional. Caso não haja certificado
que cubra o nome, o resolver configurado deve emitir um para o hostname da rota.

Validação após implantação, sem ignorar erros de certificado:

```sh
curl --fail --show-error https://tab5api.ampere.diadiatech.com.br/health/ready
```

Ainda não houve acesso SSH, alteração de DNS, emissão de certificado ou implantação.
O usuário confirmou funcionamento adequado do firmware 0.1.1 em 08/10/2026.

Referência: [labels e rede do provider Docker](https://doc.traefik.io/traefik/reference/routing-configuration/other-providers/docker/).
