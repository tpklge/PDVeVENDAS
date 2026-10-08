# Wi-Fi

Implementado no firmware candidato v0.3.0: ESP-Hosted 1.4.0/esp_wifi_remote 0.8.5
com ESP32-C6 via SDIO. Não há rádio interno no P4. Compatibilidade do C6 e
funcionamento na placa ainda precisam da validação física do usuário.

Menu pesquisa SSID/RSSI, permite escolher rede/informar senha, usa DHCP e mostra
IP/gateway. Reconecta com backoff, esquece rede mediante confirmação e testa
hora/DNS/TLS/saúde. Rede e retentativas fora da tarefa LVGL,
backoff limitado e recuperação sem reinicialização. Hora NTP/RTC precede TLS.
Configuração essencial em memória interna protegida; sem senha compilada.
Ver [provisionamento](authentication.md). O usuário escolheu desbloquear a
configuração criptografada com admin-local após cada reinício.
