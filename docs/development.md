# Desenvolvimento

Diretório: TAB5_ERP. Plataforma: ESP-IDF 5.4.4 / target esp32p4 / C++17.
Nesta máquina o SDK existe em `/Users/paludo/esp/esp-idf`, mas não estava no PATH.
Não alterar nem atualizar esse SDK compartilhado para mudar o build do projeto.

```sh
source /Users/paludo/esp/esp-idf/export.sh
cd firmware
idf.py set-target esp32p4
idf.py build
```

Em outra máquina, instalar [ESP-IDF v5.4.4](https://github.com/espressif/esp-idf/tree/v5.4.4)
com submodules e executar `install.sh esp32p4`, seguido de `export.sh`.
O Component Manager resolve o manifesto e usa `dependencies.lock`. Versionar lock;
não versionar `managed_components`, `build` ou sdkconfig gerado.

Teste portátil no Linux/macOS:

```sh
c++ -std=c++17 -Wall -Wextra -Werror firmware/tests/core_test.cpp -o /tmp/tab5-erp-core-test
/tmp/tab5-erp-core-test
```

No macOS desta sessão, o linker não aceita o SDK 27 padrão. O mesmo teste foi
compilado com `-isysroot /Library/Developer/CommandLineTools/SDKs/MacOSX15.4.sdk`
e executado com sucesso. Não modificar toolchains globais para corrigir isso.

CI executa núcleo C++ e build ESP-IDF; não substitui testes reais de teclado/touch.
Análise de secrets própria bloqueia paths privados e padrões de chave; não equivale
a auditoria de segurança completa. Dependências devem ser revistas a cada etapa,
com pins atualizados somente junto de testes e relatório de compatibilidade.

Git remote: https://github.com/tpklge/PDVeVENDAS.git. Foi encontrado vazio pelo Git.
GitHub CLI sem autenticação nesta sessão; o push será tentado pelo Git normal.
Nunca imprimir tokens nem executar force push. Credenciais/backup não pertencem ao Git.
