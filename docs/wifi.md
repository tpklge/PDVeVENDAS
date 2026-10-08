# Wi-Fi

Não implementado na v0.1.0. Integração prevista na v0.3.0: ESP-Hosted/esp_wifi_remote
com ESP32-C6 via SDIO. Não há rádio interno no P4.

Menu deverá pesquisar SSID, RSSI, informar senha, DHCP/IP/gateway/DNS, reconectar,
esquecer rede e diagnosticar DNS/TLS/saúde. Rede e retentativas fora da tarefa LVGL,
backoff limitado e recuperação sem reinicialização. Hora NTP/RTC precede TLS.
Configuração essencial em memória interna protegida; sem senha compilada.
