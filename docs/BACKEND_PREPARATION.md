# Preparação local de backend (não é uma release)

Trabalho iniciado com o anexo parcial e separado após recebimento do plano completo.
Não publicar como v0.1.0: essa versão corresponde exclusivamente à plataforma Tab5.

10 testes locais de API/credenciais/RBAC aprovados em Python 3.14 e SQLite.
Containers, MariaDB, HTTPS real, backup/restauração e consumo ARM64 ainda não validados.
O schema distribuído é somente autenticação/RBAC; não é o schema final comercial.
Servidor alvo: OCI Ampere ARM64. Credenciais são geradas apenas no provisionamento.
Reintegrar por commits revisados nas etapas v0.2.0 e v0.3.0, sem reescrever a plataforma.
