"""Storage, antivírus e retenção de documentos (§6.6).

Acrescenta a `documents` o que faltava para o arquivo deixar de ser um caminho
no disco de um servidor específico:

- `storage_backend` — onde o binário mora (`local`, `s3`);
- os campos de antivírus, com padrão `nao_verificado`. Documentos que já
  estavam no banco não passaram por varredura alguma, e é exatamente isso que
  o valor padrão diz. Marcá-los como limpos seria inventar um fato;
- `retention_until`, `purged_at` e `purge_reason`, que sustentam o expurgo do
  binário **sem** apagar o registro (§3.5).

Revision ID: b39da2ae6a7a
Revises: d259cb880f7b
Create Date: 2026-08-06 22:25:28.359983
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b39da2ae6a7a"
down_revision: Union[str, Sequence[str], None] = "d259cb880f7b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


COLUMN_NAMES = (
    "storage_backend",
    "antivirus_status",
    "antivirus_engine",
    "antivirus_engine_version",
    "antivirus_signature",
    "antivirus_scanned_at",
    "retention_until",
    "purged_at",
    "purge_reason",
)


def _new_columns():
    """Colunas recém-instanciadas.

    Um objeto `Column` fica ligado à tabela em que é usado, então não pode ser
    reaproveitado entre `upgrade` e `downgrade` — daí a fábrica.
    """
    return [
        sa.Column("storage_backend", sa.String(20), nullable=False, server_default="local"),
        sa.Column(
            "antivirus_status",
            sa.String(30),
            nullable=False,
            server_default="nao_verificado",
        ),
        sa.Column("antivirus_engine", sa.String(80), nullable=True),
        sa.Column("antivirus_engine_version", sa.String(120), nullable=True),
        sa.Column("antivirus_signature", sa.String(255), nullable=True),
        sa.Column("antivirus_scanned_at", sa.DateTime(), nullable=True),
        sa.Column("retention_until", sa.DateTime(), nullable=True),
        sa.Column("purged_at", sa.DateTime(), nullable=True),
        sa.Column("purge_reason", sa.String(255), nullable=True),
    ]


def upgrade() -> None:
    with op.batch_alter_table("documents") as batch:
        for column in _new_columns():
            batch.add_column(column)


def downgrade() -> None:
    with op.batch_alter_table("documents") as batch:
        for name in COLUMN_NAMES:
            batch.drop_column(name)
