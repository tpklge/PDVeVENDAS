# Histórico

## 0.4.0 — interface principal (candidata)

- Dashboard, menus, navegação por toque/teclado e sessão integrada.
- Temas claro/escuro persistidos no microSD e indicadores Wi-Fi/API.
- Módulos comerciais sinalizados como indisponíveis; sem dados fictícios.
- Etapa 0.3 validada no dispositivo: login, PIN e persistência microSD.

## 0.3.2 — senha ERP simplificada (candidata)

- ERP aceita 8 caracteres, sem requisitos de composição.
- Troca pelo terminal, sem eco, revoga sessões e dispensa repetir a senha inicial.
- Firmware informa falhas de sessão, validação e conexão na troca de senha.

## 0.3.1 — Wi-Fi, interface e microSD (candidata)

- Autoteste de boot mais rápido; criptografia das configurações preservada.
- Mensagem imediata, placeholders ocultos, legendas centralizadas e tema claro.
- Senha local mínima de 4 caracteres; requisito ERP permanece em 20.
- Configurações criptografadas no microSD, sem NVS, com cópia de recuperação.
- Rádio remoto selecionado como ESP32-C6: corrige assert e reinício na pesquisa Wi-Fi.

## 0.3.0 — administração e autenticação (candidata)

- Primeiro boot, admin-local e configurações criptografadas AES-GCM/PBKDF2.
- Wi-Fi remoto C6, pesquisa/seleção de redes, NTP e HTTPS verificado.
- Login ERP, troca obrigatória, sessões, perfis/permissões, refresh e logout.
- Troca local, bloqueio, confirmações de recuperação e diagnóstico preservado.
- Registro privado de credencial de dispositivo; sem segredo no firmware/Git.
- Aprovação depende da validação física no Tab5.

## 0.2.0 — infraestrutura aprovada

- MariaDB, SQL inicial, migrações, API e Traefik existente implantados no OCI.
- HTTPS validado pelo usuário com certificado Let's Encrypt e health ready.
- Secrets de arquivo, healthchecks, backup e restauração.
- Verificação de persistência e restauração isolada; CI Docker AMD64/ARM64.
- Validação final no OCI aprovada: persistência, backup restaurado e HTTPS.
- Firmware permanece em 0.1.1.

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
