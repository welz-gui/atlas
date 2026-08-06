"""Idempotência para a operação de campo offline (§3.7).

O aplicativo de campo grava diário e tarefas sem rede e reenvia quando a
conexão volta. Sem chave de idempotência, uma resposta perdida no caminho
produziria dois diários para o mesmo dia — e diário de obra é documento com
valor probatório.

Revision ID: 2fadf9863638
Revises: 0256bb2ecea6
Create Date: 2026-08-06
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2fadf9863638"
down_revision: Union[str, Sequence[str], None] = "0256bb2ecea6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for table in ("daily_logs", "task_items"):
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column("client_token", sa.String(64), nullable=True))
        op.create_index(f"ix_{table}_client_token", table, ["client_token"])


def downgrade() -> None:
    for table in ("daily_logs", "task_items"):
        op.drop_index(f"ix_{table}_client_token", table_name=table)
        with op.batch_alter_table(table) as batch:
            batch.drop_column("client_token")
