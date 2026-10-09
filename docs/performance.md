# Desempenho — sem medições no dispositivo ainda

Valores de heap/PSRAM livre e uptime são apresentados em diagnóstico a cada segundo.
São dados reais do firmware quando executado, não medições feitas nesta sessão.
Nenhuma latência de teclado/touch, memória em navegação, boot ou consumo ARM64 foi
medida. Metas de responsividade não equivalem a resultados.

Medir no Tab5: tempo de boot, tecla→renderização, touch, heap mínimo, fragmentação,
memória após 1000 trocas de página, remoção SD e estabilidade por 8 horas.
Medir servidor OCI após v0.2: RAM/CPU/latência p95, conexões e backup sob carga.

## Desbloqueio — otimização 0.9.0

PBKDF2 mantém 200.000 iterações. Em vez de pausar a cada 512 iterações (390
pausas), consulta o relógio em lotes e pausa um tick somente após 40 ms desde
a última pausa. Mantém a oportunidade para tarefas de UI/idle; nenhum parâmetro
criptográfico muda. Referência: [FreeRTOS ESP-IDF 5.4.4](https://docs.espressif.com/projects/esp-idf/en/v5.4.4/esp32p4/api-reference/system/freertos_idf.html).
Serial: `KDF local: <ms> ms; pausas: <n>`, sem PIN/salt/chaves.
Wi-Fi/NTP/HTTPS permanecem iguais. A métrica cobre o cálculo da chave, não a
conexão posterior. Ganho real ainda não medido no Tab5; comparar desbloqueios
com mesmo cartão e condições equivalentes antes/depois, incluindo interação
com teclado/touch durante a espera.

Em 09/10/2026, o usuário relatou que o desbloqueio pareceu mais rápido após o OTA
0.9.0. Evidência qualitativa; não foi informado tempo medido nem percentual de ganho.
