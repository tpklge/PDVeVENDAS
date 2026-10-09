# TAB5 ERP

ERP comercial e PDV nativo para M5Stack Tab5, em desenvolvimento incremental.
Especificação integral: [docs/REQUISITOS_RECEBIDOS.md](docs/REQUISITOS_RECEBIDOS.md).

A etapa atual é **v0.6.0 — clientes e fornecedores (candidata)**, na branch
`release/v0.6.0-customers`. Ver [provisionamento/testes](docs/authentication.md).
O firmware tem primeiro boot, desbloqueio local, configuração criptografada,
Wi-Fi e login ERP. O usuário validou cadastro, consulta, persistência após reinício,
edição, desativação/reativação e filtros. Ver [validação de produtos](docs/releases/v0.5.0.md).
Clientes/fornecedores aguardam teste no Tab5; ver [etapa 0.6](docs/releases/v0.6.0.md).

A etapa **v0.2.0 — infraestrutura** está aprovada.
API/MariaDB e HTTPS via Traefik existente foram comprovados pelo usuário no OCI.
CI com MariaDB real aprovou persistência e restauração em AMD64/ARM64; a
verificação final no OCI também passou. Etapa aprovada. Ver [stack](docker/README.md)
e [relatório](docs/releases/v0.2.0.md).

O firmware candidato é **v0.6.0**, mantendo a plataforma validada em v0.1.1.
Display/LVGL, teclado I²C, touchscreen, menu de diagnóstico e montagem não destrutiva
do microSD estão implementados. O usuário confirmou instalação e as três telas no dispositivo; esta revisão corrige os acentos.
Esta etapa não registra vendas e não emite documentos fiscais.

O servidor está **na nuvem OCI Ampere ARM64**. Docker não precisa
ser instalado neste computador para desenvolver o firmware. API/MariaDB/Traefik
pertencem à etapa v0.2.0 e o assistente/login no Tab5 à v0.3.0.

Preparação antecipada original preservada na branch local
`work/backend-preparation`, commit `d25cc17`; sua fundação agora integra esta etapa.

```sh
cd firmware
source /Users/paludo/esp/esp-idf/export.sh
idf.py set-target esp32p4
idf.py build
# Somente com Tab5 conectado; configure a porta real:
idf.py -p PORTA_DO_TAB5 flash monitor
```

Consulte [desenvolvimento](docs/development.md), [hardware](docs/hardware.md),
[arquitetura](docs/architecture.md), [roteiro](docs/roadmap.md) e
[relatório da etapa](docs/releases/v0.1.0.md) e
[roteiro de homologação física](docs/platform-validation.md).

Código original licenciado sob MIT. Dependências mantêm suas próprias licenças.
Não queimar eFuses nem ativar segurança irreversível durante desenvolvimento.
