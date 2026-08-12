"""Reconcilia a deriva entre modelos e migrations.

Revision ID: c7a41d9e2b83
Revises: 2fadf9863638
Create Date: 2026-08-12

Havia dois caminhos para construir o esquema, e eles divergiram: a suíte monta o
banco com `Base.metadata.create_all` a partir dos modelos, enquanto produção usa
`alembic upgrade head`. Os testes rodavam contra um esquema que produção não
tinha.

Os índices compostos passam a existir também nos modelos — mudança que não toca
o banco, porque as migrations já os criavam. O que esta migration faz é a outra
metade: três colunas que os modelos declaram obrigatórias estavam permissivas no
banco.

`retrieved_rule_keys`, `cited_rule_keys` e `payload` são sempre escritas pelo
código, com lista ou dicionário vazio quando não há conteúdo — ver
`ai/service.py` e `workers/queue.py::enqueue`, que faz `payload or {}`. Lista
vazia significa "nada foi recuperado"; `NULL` não significa nada, e os dois
seriam indistinguíveis em auditoria. Daí o `NOT NULL`.

O backfill precede a alteração: linha antiga com `NULL` viraria erro de
constraint no meio do upgrade.
"""

from alembic import op
import sqlalchemy as sa

revision = "c7a41d9e2b83"
down_revision = "2fadf9863638"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Backfill antes da constraint. Sem isto, um banco com histórico de IA
    # anterior a esta migration falharia no meio do upgrade.
    op.execute(
        "UPDATE ai_interactions SET retrieved_rule_keys = '[]' "
        "WHERE retrieved_rule_keys IS NULL"
    )
    op.execute(
        "UPDATE ai_interactions SET cited_rule_keys = '[]' "
        "WHERE cited_rule_keys IS NULL"
    )
    op.execute("UPDATE job_records SET payload = '{}' WHERE payload IS NULL")

    with op.batch_alter_table("ai_interactions") as batch:
        batch.alter_column("retrieved_rule_keys", existing_type=sa.JSON(), nullable=False)
        batch.alter_column("cited_rule_keys", existing_type=sa.JSON(), nullable=False)

    with op.batch_alter_table("job_records") as batch:
        batch.alter_column("payload", existing_type=sa.JSON(), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("job_records") as batch:
        batch.alter_column("payload", existing_type=sa.JSON(), nullable=True)

    with op.batch_alter_table("ai_interactions") as batch:
        batch.alter_column("cited_rule_keys", existing_type=sa.JSON(), nullable=True)
        batch.alter_column("retrieved_rule_keys", existing_type=sa.JSON(), nullable=True)
