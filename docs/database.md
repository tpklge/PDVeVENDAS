# Banco de dados

Arquitetura alvo: MariaDB 11.8 LTS/InnoDB/utf8mb4, UTC, DECIMAL para dinheiro e
chaves estrangeiras/índices. Cliente acessa somente API. Migrações com Alembic.

Não existe banco operacional nesta branch da plataforma. O schema de autenticação
preparado está isolado na branch local work/backend-preparation. Não representa
o schema comercial completo e não deve ser apresentado como banco final do ERP.

O schema completo evoluirá na v0.2.0 e módulos posteriores, com SQL equivalente
às revisões e testes MariaDB reais: volume vazio, volume existente, integridade,
privilégios mínimos, backup/restore e concorrência. A API usa usuário CRUD separado
do usuário DDL; nenhum deles terá GRANT OPTION ou administração global.
