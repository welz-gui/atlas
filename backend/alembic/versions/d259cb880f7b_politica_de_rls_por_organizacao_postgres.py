"""Política de RLS por organização (Postgres).

Segunda linha de defesa para o isolamento entre tenants (§3.1, §12). A
aplicação já filtra por `organization_id` em `app/api/deps.py`; a RLS garante
que um erro de programação — um `query()` sem filtro — não vire vazamento
entre organizações.

Em SQLite a migration é um no-op: o motor não suporta RLS, e o
desenvolvimento local continua dependendo apenas do filtro de aplicação.

**Para a RLS ter efeito é preciso**, além desta migration:

1. conectar a aplicação com um usuário **sem** BYPASSRLS (o dono da tabela e
   superusuários ignoram a política);
2. definir `atlas.organization_id` por transação, a partir do usuário
   autenticado::

       SET LOCAL atlas.organization_id = '<uuid da organização>';

   O lugar natural é um listener de `begin` na sessão do SQLAlchemy.

Sem o passo 2, `current_setting(..., true)` devolve NULL e a política nega
tudo — comportamento deliberado: falhar fechado é preferível a abrir por
omissão.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "d259cb880f7b"
down_revision: Union[str, Sequence[str], None] = "a2e165918066"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

#: Tabelas que carregam `organization_id`.
TENANT_TABLES = (
    "projects",
    "project_versions",
    "documents",
    "analysis_runs",
    "validation_records",
    "protocol_processes",
    "protocol_requirements",
    "protocol_events",
    "eap_items",
    "task_items",
    "daily_logs",
    "users",
)


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return

    preparer = op.get_bind().dialect.identifier_preparer
    for table in TENANT_TABLES:
        table_q = preparer.quote(table)
        policy_q = preparer.quote(f"{table}_tenant_isolation")

        op.execute(f"ALTER TABLE {table_q} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table_q} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY {policy_q} ON {table_q}
            USING (organization_id = current_setting('atlas.organization_id', true))
            WITH CHECK (organization_id = current_setting('atlas.organization_id', true))
            """
        )


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return

    preparer = op.get_bind().dialect.identifier_preparer
    for table in TENANT_TABLES:
        table_q = preparer.quote(table)
        policy_q = preparer.quote(f"{table}_tenant_isolation")
        op.execute(f"DROP POLICY IF EXISTS {policy_q} ON {table_q}")
        op.execute(f"ALTER TABLE {table_q} DISABLE ROW LEVEL SECURITY")
