"""Proveniência de interações de IA (§3.3, §3.5, §6.8).

Toda chamada a modelo de linguagem deixa registro: quem perguntou, o que foi
perguntado, quais regras do catálogo foram entregues como contexto, quais foram
citadas na resposta e se a resposta se sustentou nesse contexto (`grounded`).

`answer_is_advisory` é invariante, não configuração — nada que saia de um
modelo tem valor de veredicto (§3.4). A coluna existe para que nenhuma consulta
futura precise supor isso.

Revision ID: 0256bb2ecea6
Revises: 48600ee76c7c
Create Date: 2026-08-06
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0256bb2ecea6"
down_revision: Union[str, Sequence[str], None] = "48600ee76c7c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_interactions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("purpose", sa.String(60), nullable=False, server_default="consulta_normativa"),
        sa.Column("provider", sa.String(60), nullable=False),
        sa.Column("model", sa.String(120), nullable=True),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("retrieved_rule_keys", sa.JSON(), nullable=True),
        sa.Column("cited_rule_keys", sa.JSON(), nullable=True),
        sa.Column("response_text", sa.Text(), nullable=True),
        sa.Column("response_json", sa.JSON(), nullable=True),
        sa.Column("stop_reason", sa.String(60), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("grounded", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "answer_is_advisory", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
        sa.Column(
            "served_from_cache", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.String(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_ai_interactions_organization_id", "ai_interactions", ["organization_id"]
    )
    op.create_index("ix_ai_interactions_project_id", "ai_interactions", ["project_id"])
    # O cache procura por (organização, hash da requisição); sem este índice a
    # busca varreria todo o histórico a cada consulta.
    op.create_index(
        "ix_ai_interactions_org_hash",
        "ai_interactions",
        ["organization_id", "request_hash"],
    )


def downgrade() -> None:
    op.drop_index("ix_ai_interactions_org_hash", table_name="ai_interactions")
    op.drop_index("ix_ai_interactions_project_id", table_name="ai_interactions")
    op.drop_index("ix_ai_interactions_organization_id", table_name="ai_interactions")
    op.drop_table("ai_interactions")
