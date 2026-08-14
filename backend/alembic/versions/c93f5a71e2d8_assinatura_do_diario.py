"""Assinatura do diário de obra (§8.12 — D4).

Revision ID: c93f5a71e2d8
Revises: b6c8d2f40a19
Create Date: 2026-08-14

Até aqui `status` nascia como `"assinado"` por `default`, e o frontend ainda
mandava a string literal. Era afirmação falsa em duas camadas: todo diário
alegava um ato humano que nunca houve — inclusive os criados pela fila offline,
quando ninguém estava diante de tela alguma.

O `UPDATE` abaixo corrige o passado da única forma honesta disponível: os
diários existentes **não foram assinados**, então voltam a `rascunho`. Marcá-los
como assinados por alguém exigiria inventar quem e quando.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c93f5a71e2d8"
down_revision: Union[str, Sequence[str], None] = "b6c8d2f40a19"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # `batch_alter_table` porque o SQLite não altera constraint no lugar, e
    # `signed_by_id` carrega chave estrangeira. Em Postgres o batch é
    # transparente; em SQLite ele recria a tabela e copia.
    with op.batch_alter_table("daily_logs") as batch:
        batch.add_column(sa.Column("content_hash", sa.String(64), nullable=True))
        batch.add_column(sa.Column("signed_by_id", sa.String(), nullable=True))
        batch.add_column(sa.Column("signed_by_name", sa.String(255), nullable=True))
        batch.add_column(sa.Column("signed_at", sa.DateTime(), nullable=True))
        batch.create_foreign_key(
            "fk_daily_logs_signed_by_id", "users", ["signed_by_id"], ["id"]
        )

    op.create_index("ix_daily_logs_status", "daily_logs", ["status"])

    # Nenhum diário existente foi de fato assinado. Dizer o contrário seria
    # manter a mentira que esta migration existe para desfazer.
    op.execute("UPDATE daily_logs SET status = 'rascunho' WHERE status = 'assinado'")


def downgrade() -> None:
    op.drop_index("ix_daily_logs_status", table_name="daily_logs")
    with op.batch_alter_table("daily_logs") as batch:
        batch.drop_constraint("fk_daily_logs_signed_by_id", type_="foreignkey")
        batch.drop_column("signed_at")
        batch.drop_column("signed_by_name")
        batch.drop_column("signed_by_id")
        batch.drop_column("content_hash")
    op.execute("UPDATE daily_logs SET status = 'assinado' WHERE status = 'rascunho'")
