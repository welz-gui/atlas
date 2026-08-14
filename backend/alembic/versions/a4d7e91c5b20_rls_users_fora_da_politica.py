"""Tira `users` da política de RLS, porque a autenticação a precede.

Revision ID: a4d7e91c5b20
Revises: f1a2b3c4d5e6
Create Date: 2026-08-14

A política de `d259cb880f7b` incluiu `users`. Ao ativar a RLS de fato (item D1)
isso se mostrou impossível de sustentar, e a razão é estrutural, não de
implementação:

**A autenticação é anterior ao tenant.** Duas consultas a `users` acontecem
necessariamente sem organização em contexto:

- `POST /auth/login` procura o usuário **por e-mail**, e é justamente daí que a
  organização vem. Não há como saber o tenant antes de encontrar a linha;
- `POST /auth/signup` verifica se o e-mail já existe **em qualquer
  organização**, porque e-mail é único globalmente. A consulta é
  cross-tenant por definição.

Com `users` sob RLS e `FORCE ROW LEVEL SECURITY`, as duas devolveriam zero
linhas e o sistema ficaria sem porta de entrada.

**O que continua protegido.** Todas as tabelas que carregam trabalho de cliente
— projetos, versões, documentos, análises, tramitação, obra — seguem sob a
política. É onde um vazamento exporia o que o cliente pagou para produzir.

**O que fica com uma linha de defesa só.** A listagem de usuários passa a
depender apenas do filtro de aplicação (`api/deps.py::tenant_query`), que tem
teste de isolamento respondendo 404. É defesa em profundidade a menos, e está
registrado no roadmap como tal.

**Como fechar essa lacuna depois**, se o risco justificar: uma conexão
dedicada, com papel que tenha `BYPASSRLS`, usada exclusivamente pelos dois
caminhos de autenticação acima — mantendo `users` sob política para todo o
resto. Custa uma segunda `DATABASE_URL` e a disciplina de nunca usá-la fora
dali.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "a4d7e91c5b20"
down_revision: Union[str, Sequence[str], None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return

    op.execute("DROP POLICY IF EXISTS users_tenant_isolation ON users")
    op.execute("ALTER TABLE users NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE users DISABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return

    op.execute("ALTER TABLE users ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE users FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY users_tenant_isolation ON users
        USING (organization_id = current_setting('atlas.organization_id', true))
        WITH CHECK (organization_id = current_setting('atlas.organization_id', true))
        """
    )
