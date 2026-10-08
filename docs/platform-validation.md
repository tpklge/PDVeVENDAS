# Homologação física da plataforma v0.1.0

Esta lista ainda não foi executada. O Tab5 não apareceu nas portas USB do host.
Anotar revisão da placa, painel/touch, versão do teclado, modelo/capacidade do SD,
hash do BIN, alimentação e log serial em cada execução.

| Verificação | Como executar | Evidência de aprovação |
|---|---|---|
| Boot | Gravar por USB sem erase_flash, reiniciar | Log versão/SDK, sem panic/reset repetido |
| Display | Abrir três páginas | Conteúdo 1280×720 paisagem, sem cortes/inversão |
| Touch | Tocar botões e campo de teste | Contador cresce, seleção corresponde à posição |
| Teclado | Conectar antes do boot, abrir teste | Versão detectada, letras/números/símbolos corretos |
| Navegação | Tab/Shift+Tab, setas, Enter, Esc | Foco visível, menus ativados, Esc volta ao diagnóstico |
| Sem teclado | Boot com teclado desconectado | Teclado virtual na página de teste, menu utilizável |
| SD presente | Cartão FAT compatível antes do boot | Montado, escrita verificada, /ERP/logs/platform.log legível |
| Sem SD | Boot sem cartão | Aviso de indisponível, nenhum formato/loop de reset |
| SD inválido | Cartão descartável incompatível | Erro informado, dados não formatados automaticamente |
| Estabilidade | 1000 navegações / 8 h em diagnóstico | Heap sem tendência de queda, sem watchdog/reset |
| NVS | Reiniciar com partição existente válida | Sem erase automático ou perda por boot normal |

Não digitar senhas reais no teste de entrada. Não remover SD durante escrita para
uso normal; ensaios de falha de energia/corrupção serão controlados na v0.11.0.
Esta etapa não valida transações, rede, HTTPS, login, admin-local ou M5Launcher.
O roteiro completo deve seguir só após causas de falhas de inicialização documentadas.
