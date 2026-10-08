# Hardware e compatibilidade

Fontes oficiais consultadas em 08/10/2026:

- [Tab5 M5Stack](https://docs.m5stack.com/en/core/Tab5).
- [BSP Espressif Tab5](https://github.com/espressif/esp-bsp/tree/master/bsp/m5stack_tab5).
- [Tab5 Keyboard](https://docs.m5stack.com/en/tab5/Tab5_Keyboard).
- [Exemplo oficial teclado](https://docs.m5stack.com/en/arduino/projects/tab5/tab5_keyboard).
- [Protocolo/implementação oficial teclado](https://github.com/m5stack/M5Unit-KEYBOARD/tree/main/src/unit).

ESP32-P4 RISC-V dual core, 16 MiB flash, 32 MiB PSRAM, display MIPI-DSI 5 polegadas.
O painel tem orientação física 720×1280; a aplicação gira para 1280×720.
Revisões de tela e touch variam; BSP 1.3.2 suporta ILI9881C/ST7123 e GT911/ST7123.
A identificação real da revisão e a calibração precisam de teste em placa.

| Interface | GPIO / endereço |
|---|---|
| I²C interno BSP | SDA31 / SCL32 / controlador 1 |
| Tab5 Keyboard ExtPort1 | SDA0 / SCL1 / controlador 0 / 0x6D |
| Interrupção teclado | GPIO50, ativo baixo |
| microSD SDMMC | D0 39, D1 40, D2 41, D3 42, CLK43, CMD44 |
| Touch INT / backlight | GPIO23 / GPIO22 |

Driver do teclado configura HID: modo 0x10=1, habilita INT HID em 0x00=2,
consulta contagem 0x02, lê modifier/keycode em 0x30 e limpa INT em 0x01.
Lê versão em 0xFE. Normal e Character não são selecionados nesta etapa.
A ISR só notifica a tarefa; não executa I²C nem LVGL. Teclas comuns, Tab/Shift+Tab,
setas, Enter, Esc, Backspace e Delete são traduzidas; F1–F10 requerem validação
das combinações reais do Tab5 Keyboard e serão integradas conforme o módulo.
HID US ASCII não resolve composição de acentos: ampliar entrada pt-BR na v0.4.0.

Sem teclado, tela de teste oferece teclado virtual. Sem microSD, menu permanece
operante. Nenhum cartão é formatado automaticamente. Logs da plataforma não
contêm caracteres digitados. Firmware não tenta autenticar nem acessar ERP.

## Wi-Fi e relógio (próxima etapa)

O P4 não tem rádio; C6 via SDIO exige [ESP-Hosted](https://github.com/espressif/esp-hosted-mcu)
e `esp_wifi_remote`. Evitar reutilizar código de rádio integrado de ESP32-S3.
RTC RX8130CE é externo; temporizador RTC do SoC não equivale a relógio civil persistente.
SNTP mais RTC devem assegurar hora antes de TLS; sem hora confiável, exibir erro,
sem remover a verificação do certificado.

## Launcher

[Lista oficial do projeto Launcher](https://github.com/bmorcelli/Launcher/wiki/Supported-devices)
informa Tab5 desde 2.6.0. Isso não prova que o nosso BIN possa ser instalado.
Partições de desenvolvimento: NVS/otadata/phy + dois slots OTA de 6 MiB + storage.
Testar offsets, tamanho, bootloader, preservação de NVS e firmware C6 antes de
publicar instruções ou imagem mesclada para Launcher. A v0.1 usa gravação USB.
