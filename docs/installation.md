# Instalação — plataforma e servidor futuro

A v0.1.0 instala apenas firmware por USB; não há instalador completo de ERP.
Compilar conforme development.md e usar porta do Tab5 em `idf.py -p PORTA flash monitor`.
O monitor permite verificar erros de BSP/teclado/SD e mensagem de versão.
Nenhuma gravação foi feita automaticamente no dispositivo nesta sessão.

O servidor alvo é OCI Ampere ARM64. Docker Engine e Compose Plugin serão instalados
no servidor Ubuntu/Debian, conforme [Ubuntu](https://docs.docker.com/engine/install/ubuntu/)
e [Debian](https://docs.docker.com/engine/install/debian/). O Docker não foi instalado
nem executado neste computador. O usuário informou Ubuntu, kernel 6.17, possivelmente
Ubuntu 24.04; a versão ainda precisa ser confirmada. A API usará
`tab5api.ampere.diadiatech.com.br` atrás do Traefik existente. Acesso SSH ainda
não informado. Ver [preparação OCI](server-oci.md) e [Traefik](traefik.md).

Perfil inicial para medir: 2 vCPU, 2 GiB RAM e pelo menos 20 GiB de disco persistente.
Não é uma garantia de capacidade. Registrar consumo após carga e backups reais.
Preparar DNS A/AAAA coerente com IPv4/IPv6 do servidor, portas 80/443 TCP e saída
para ACME/atualizações. Restringir SSH na Security List/NSG da OCI e firewall do host.
Nunca liberar 3306 publicamente; API e MariaDB não terão ports publicados.

Compose/scripts de servidor serão integrados e documentados na v0.2.0, com migrações,
healthchecks, atualização, backup e restauração testados. Credenciais devem ser
criadas no servidor durante provisionamento, com cópia protegida fora do Git.
