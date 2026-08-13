"""Retenção de conteúdo de IA e trabalhos, e marca de anonimização.

Revision ID: e8f2a1c60d47
Revises: c7a41d9e2b83
Create Date: 2026-08-12

Três colunas, todas com o mesmo desenho: **marcam que algo foi removido, em vez
de remover a linha.**

`ai_interactions.content_purged_at` e `job_records.content_purged_at` registram
quando a pergunta, a resposta e o payload foram descartados pela retenção. A
proveniência fica: modelo, tokens, regras recuperadas, se a resposta estava
fundamentada, quando aconteceu. É o mesmo contrato do §6.6 para documentos —
sai o conteúdo, permanece o registro.

`projects.anonymized_at` e `projects.anonymization_reason` registram o
atendimento a um pedido de eliminação de dado pessoal de terceiro (proprietário,
contratante, responsável técnico). Análises e versões são append-only (I5, I6) e
continuam existindo: o que sai é o nome, não a trilha.
"""

from alembic import op
import sqlalchemy as sa

revision = "e8f2a1c60d47"
down_revision = "c7a41d9e2b83"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ai_interactions",
        sa.Column("content_purged_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "job_records",
        sa.Column("content_purged_at", sa.DateTime(), nullable=True),
    )
    op.add_column("projects", sa.Column("anonymized_at", sa.DateTime(), nullable=True))
    op.add_column(
        "projects", sa.Column("anonymization_reason", sa.Text(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("projects", "anonymization_reason")
    op.drop_column("projects", "anonymized_at")
    op.drop_column("job_records", "content_purged_at")
    op.drop_column("ai_interactions", "content_purged_at")
