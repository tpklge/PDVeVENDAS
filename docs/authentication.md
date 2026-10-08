# Etapa 0.3.0 — provisionamento e teste no Tab5

Firmware candidato 0.3.0; API 0.2.0 já implantada é compatível (`api_version=v1`,
capabilities auth/rbac). Não é necessário reconstruir a API para este teste.

## Administrador ERP no servidor

No OCI, a partir de `/home/ubuntu/TAB5_ERP`, executar uma única vez:

```sh
bash docker/scripts/initialize.sh
```

O comando usa o secret já gerado, cria `admin` com perfil Administrador e exige
troca da senha no primeiro login. Recusa alterar usuários se já houver cadastro;
nesse caso usar a conta existente, sem apagar banco/volume. Consultar a senha
inicial apenas localmente em `docs/private/INITIAL_CREDENTIALS.md`; não enviá-la
ao chat nem publicar. O firmware nunca recebe credenciais SQL.

## Primeiro boot

1. Instalar o firmware 0.3.0 mantendo as partições existentes de 16 MiB.
2. O autoteste verifica PBKDF2 contra um vetor conhecido, AES-GCM roundtrip e
   rejeição de tag adulterada; falha bloqueia o provisionamento.
   Aguardar alguns segundos para a primeira tela de acesso enquanto ele executa.
3. Criar admin-local. Preferir a senha `local_admin_password` reservada no relatório
   privado do servidor, digitando-a no lugar da sugestão. Alternativamente guardar
   a senha de 24 caracteres sugerida pelo Tab5 e registrar em relatório privado:

```sh
python3 tools/record_device_credentials.py --root . --device TAB5_1
```

O utilitário solicita a senha sem eco e não a imprime. A senha local deve ter
pelo menos 20 caracteres; é independente da senha ERP.

4. Pesquisar redes, selecionar SSID ou digitar manualmente, informar a senha Wi-Fi
   e conferir `https://tab5api.ampere.diadiatech.com.br`. Salvar e conectar.
5. A conexão aguarda DHCP, sincroniza hora por NTP, valida a cadeia/hostname TLS,
   testa health ready e compatibilidade da API. Sem horário confiável, TLS falha.
6. Entrar com administrador ERP; trocar a senha inicial por uma diferente com
   pelo menos 20 caracteres e entrar novamente. A API revoga sessões na troca.
7. A primeira instalação só é marcada concluída após login com permissão
   `users.create`, sem troca obrigatória pendente e configuração persistida.
8. Conferir usuário, dispositivo, perfis e permissões na área de sessão (rolável).
   Sair revoga a família da sessão no servidor. Se a revogação não for confirmada
   por falha de rede, a tela informa isso e remove os tokens do dispositivo.

## Desbloqueio após reinício

Por escolha do usuário, Wi-Fi/API ficam em envelope AES-256-GCM em NVS. A chave
é derivada da senha admin-local com PBKDF2-HMAC-SHA256, salt individual e 200.000
iterações. A derivação cede CPU periodicamente para manter interface/watchdog.
O perfil mantém a fonte de entropia ADC do P4 ativa para RNG e handshakes TLS;
não inicializa sensores ADC. Integrar ADC no futuro exige revisar esse uso.
A tag autenticada valida a senha; não existe senha ou chave de configuração
em texto puro na flash. Cada gravação usa nonce novo e commit NVS.

Depois de reiniciar, informar admin-local para desbloquear a configuração e
reconectar. O login ERP é separado. Tokens ficam em memória interna, não em
NVS/microSD. A chave e configurações abertas são removidas da RAM ao bloquear.
Há espera progressiva após falhas locais; não há senha mestre. Não são gravadas
eFuses nem ativados Secure Boot/Flash Encryption automaticamente. A proteção
resiste à leitura da configuração sem a senha, mas não impede substituir o
firmware por USB em equipamento sob controle físico.

Alterar a senha local recriptografa as configurações; guardar a nova senha e
eliminar o registro inicial antigo. Esquecer rede e restaurar configurações
exigem confirmação. Restauração na interface remove logicamente o blob NVS e
reinicia; não equivale a sanitização forense de toda a flash e preserva o banco.

## Wi-Fi e recuperação física

ESP-Hosted 1.4.0 e esp_wifi_remote 0.8.5 são as versões do exemplo oficial M5Stack;
esperam firmware compatível no C6. SDIO slot 1: CLK12/CMD13/D0=11/D1=10/D2=9/D3=8,
reset15, 25 MHz. microSD usa slot 0. BSP habilita a alimentação Wi-Fi em E2.P0;
E1.P0 é colocado em nível baixo para selecionar a antena interna.

Se pesquisa/conexão falhar, coletar log serial sanitizado; não regravar o C6
automaticamente. Não fornecer imagem de C6 incompatível só para contornar o erro.

Se a senha local for perdida, a recuperação exige posse física, conexão USB,
backup dos dados necessários e apagar explicitamente a partição NVS da aplicação
(offset 0x9000, tamanho 0x6000 no particionamento atual), após confirmação do
operador. Isso remove a configuração/credencial local e retorna ao primeiro boot;
não altera banco, SD ou firmware do C6. Não executar erase-flash completo como
procedimento padrão. Falha NVS não causa apagamento automático no firmware.

## Critérios de validação física pendentes

- Autoteste, touchscreen, teclado físico e teclado virtual operam sem travar.
- Pesquisa Wi-Fi mostra SSID/RSSI e permite escolher rede; senha correta conecta.
- Senha errada/rede ausente permitem corrigir; reconexão tem backoff limitado.
- URL inválida/certificado inválido/API incompatível não são aceitos.
- Configuração sobrevive a reinício e exige admin-local para desbloqueio.
- Administrador ERP troca senha inicial; senha anterior e sessões antigas falham.
- Login normal exibe apenas suas permissões; API responde 403 a acesso proibido.
- Refresh rotaciona tokens; replay revoga a família; logout encerra sessão.
- Troca local preserva configuração e senha antiga não desbloqueia após reinício.
- Diagnóstico e microSD continuam disponíveis; credenciais não aparecem em logs.

Testes automatizados da API cobrem troca obrigatória, revogação, refresh/replay,
device binding, RBAC, inatividade, expiração e limitação de tentativas. A aprovação
da etapa e tag 0.3.0 dependem dos testes no Tab5; não extrapolar compilação para
funcionamento físico.

Referência de versões/pinos: [exemplo oficial M5Stack](https://github.com/m5stack/M5Tab5-UserDemo/tree/main/platforms/tab5).
