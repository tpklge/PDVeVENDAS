# Plataforma nativa Tab5

Firmware ESP-IDF/C++ com LVGL, BSP oficial, teclado HID via I²C/IRQ, touchscreen,
menu de diagnóstico, teste de entrada e microSD. Esta etapa não implementa ERP.
Ver [docs/development.md](../docs/development.md) para compilar e gravar por USB.

Dependências diretas fixadas em main/idf_component.yml; árvore transitiva em
dependencies.lock. sdkconfig.defaults é desenvolvimento; não queima eFuses.
partitions.csv usa flash 16 MiB com dois slots OTA 6 MiB; Launcher ainda não homologado.

Núcleo portátil usa C++17 e testes de HID, centavos e estado do assistente. A máquina
 de estados é preparação interna; assistente local/NVS protegida não estão integrados.
Não preencher evidências com constantes para liberar configuração ou acesso ERP.
