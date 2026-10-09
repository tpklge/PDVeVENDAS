# Permissões

Servidor valida RBAC em cada endpoint. Papéis padrão Administrador, Gerente,
Vendedor e Consulta; códigos em api/app/seed.py. Atribuições existentes são
preservadas nas atualizações. Ocultar botão não substitui autorização da API.
admin-local só desbloqueia configurações; não concede sessão ou acesso comercial.

Produtos, clientes/fornecedores, vendas e estoque usam permissões próprias.
Documentos pessoais exigem .documents além da leitura. Consulta não escreve.
Gerente não administra usuários/configurações do servidor.

0.9 usa códigos existentes: cash.open para abrir, cash.close para fechar,
cash.deposit para suprimento, cash.withdraw para sangria. Consulta de caixa requer
pelo menos um desses códigos ou reports.financial; somente operador/terminal próprio.
Contas/categorias/baixas exigem reports.financial; cadastrar receita/baixar recebível
exige também cash.deposit; despesa/pagável exige cash.withdraw.
Vendedor padrão abre/fecha o próprio caixa e vende. Gerente e Administrador possuem
financeiro/sangria/suprimento. Consulta padrão não acessa caixa ou financeiro.

Não são concedidas permissões novas automaticamente na 0.9; 32 códigos existentes.
Ver [regras de caixa e contas](releases/v0.9.0.md).

0.10: reports.read em todos os relatórios; reports.financial adicional para valores
de vendas/pagamentos/cancelamentos/caixa/contas. Consulta acessa estoque e movimentos
sem preços. Não modificar papéis existentes automaticamente.
