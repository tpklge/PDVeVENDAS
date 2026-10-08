# Histórico

## 0.2.0 — infraestrutura (validação final pendente)

- MariaDB, SQL inicial, migrações, API e Traefik existente implantados no OCI.
- HTTPS validado pelo usuário com certificado Let's Encrypt e health ready.
- Secrets de arquivo, healthchecks, backup e restauração.
- Verificação de persistência e restauração isolada; CI Docker AMD64/ARM64.
- Firmware permanece em 0.1.1; aprovação final depende dos testes restantes.

## 0.1.1 — fonte pt-BR

- Corrige glifos ausentes nas fontes: Latin-1 para ç/acentos nos tamanhos 20 e 28.
- Tema e widgets usam fonte pt-BR; símbolos LVGL mantidos por fallback.
- Linha de conferência de acentos na tela de entrada.
- Instalação e três telas testadas pelo usuário; revisão visual desta correção pendente.

## 0.1.0 — plataforma (candidata; validação física pendente)

- Projeto ESP-IDF 5.4.4 para ESP32-P4 e BSP oficial fixado.
- LVGL em paisagem, menu, diagnóstico e teste de entrada.
- Driver original Tab5 Keyboard em HID, I²C e interrupção GPIO50.
- microSD sem formatação automática; teste de escrita e log limitado.
- Núcleo C++ independente do hardware, documentação e CI da plataforma.
- Preparação de backend isolada da sequência de releases.
