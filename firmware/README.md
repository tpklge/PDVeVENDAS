# Firmware TAB5 ERP 1.0.0

ESP-IDF 5.4.4/C++17, ESP32-P4, BSP oficial Tab5, LVGL, teclado físico I²C,
touchscreen e interface em português. Conexão pelo ESP32-C6 via ESP-Hosted.
PIN local, configuração/Wi-Fi e dados offline criptografados no microSD, sem NVS
para dados ERP. Login ERP separado; transações e RBAC são autoridade da API.

Dependências diretas em main/idf_component.yml, transitivas em dependencies.lock.
Mbed TLS 3.6.7 do fork Espressif é preparado no build com hash verificado, sem
alterar SDK compartilhado. Não grava eFuses ou muda a conexão/PIN nesta entrega.

partitions.csv: flash 16 MiB, dois slots OTA de 6 MiB. Distribuição pelo BIN da
aplicação, usando M5Launcher já utilizado pelo usuário. Não usar erase_flash,
formatar o microSD ou instalar bootloader como aplicação no fluxo existente.

Build em [development.md](../docs/development.md), instalação/atualização em
[installation.md](../docs/installation.md), recuperação em
[recovery.md](../docs/recovery.md), evidências e limites em
[release 1.0](../docs/releases/v1.0.0.md).
