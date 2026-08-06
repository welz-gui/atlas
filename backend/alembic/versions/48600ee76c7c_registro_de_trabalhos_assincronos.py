"""Registro de trabalhos assíncronos (§6.7).

O banco é a fonte da verdade das filas: o broker carrega apenas o
identificador. Um Redis reiniciado não apaga trabalho nenhum, e a trilha de
auditoria (§3.5) não passa a depender de um sistema externo.

Revision ID: 48600ee76c7c
Revises: b39da2ae6a7a
Create Date: 2026-08-06
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "48600ee76c7c"
down_revision: Union[str, Sequence[str], None] = "b39da2ae6a7a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "job_records",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("job_type", sa.String(60), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="enfileirado"),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column(
            "executed_inline", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("queue", sa.String(60), nullable=False, server_default="default"),
        sa.Column("worker_id", sa.String(120), nullable=True),
        sa.Column("queued_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("requested_by_id", sa.String(), sa.ForeignKey("users.id"), nullable=True),
    )
    op.create_index("ix_job_records_organization_id", "job_records", ["organization_id"])
    op.create_index("ix_job_records_project_id", "job_records", ["project_id"])
    op.create_index("ix_job_records_job_type", "job_records", ["job_type"])
    # O worker varre por (status, fila) à procura de órfãos; sem este índice a
    # varredura passaria a tabela inteira a cada partida.
    op.create_index("ix_job_records_status_queue", "job_records", ["status", "queue"])


def downgrade() -> None:
    op.drop_index("ix_job_records_status_queue", table_name="job_records")
    op.drop_index("ix_job_records_job_type", table_name="job_records")
    op.drop_index("ix_job_records_project_id", table_name="job_records")
    op.drop_index("ix_job_records_organization_id", table_name="job_records")
    op.drop_table("job_records")
