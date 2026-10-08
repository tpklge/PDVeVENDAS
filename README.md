# TAB5 ERP

ERP comercial e PDV nativo para M5Stack Tab5, em desenvolvimento incremental.
Especificação integral: [docs/REQUISITOS_RECEBIDOS.md](docs/REQUISITOS_RECEBIDOS.md).

A etapa atual é **v0.1.0 — plataforma Tab5**, na branch `release/v0.1.0-platform`.
Display/LVGL, teclado I²C, touchscreen, menu de diagnóstico e montagem não destrutiva
do microSD estão implementados. A execução no dispositivo ainda exige homologação.
Esta etapa não registra vendas, não emite documentos fiscais e não possui login.

O servidor futuro será instalado **na nuvem OCI Ampere ARM64**. Docker não precisa
ser instalado neste computador para desenvolver o firmware. API/MariaDB/Caddy
pertencem à etapa v0.2.0 e autenticação à v0.3.0.

Preparação antecipada do backend foi preservada apenas na branch local
`work/backend-preparation`, commit `d25cc17`. Não faz parte da release de plataforma.

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
