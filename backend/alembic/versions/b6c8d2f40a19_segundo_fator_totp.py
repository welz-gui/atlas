"""Segundo fator por TOTP e códigos de recuperação (§8.1, §12 — D2).

Revision ID: b6c8d2f40a19
Revises: a4d7e91c5b20
Create Date: 2026-08-14

`users.mfa_secret` guarda o segredo **cifrado** — ver `core/mfa.py`. Em claro,
qualquer cópia do banco geraria códigos válidos indefinidamente.

`mfa_activated_at` separa "gerou o segredo" de "confirmou com um código". Só o
segundo conta como segundo fator: quem gera o QR Code e fecha a aba não está
protegido, e o sistema não pode fingir que está.

`mfa_recovery_codes` guarda o hash, nunca o código. `used_at` marca o consumo em
vez de apagar a linha, para que o uso fique no histórico (§3.5).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b6c8d2f40a19"
down_revision: Union[str, Sequence[str], None] = "a4d7e91c5b20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("mfa_secret", sa.String(255), nullable=True))
    op.add_column(
        "users", sa.Column("mfa_activated_at", sa.DateTime(), nullable=True)
    )

    op.create_table(
        "mfa_recovery_codes",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column("code_hash", sa.String(255), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_mfa_recovery_codes_user_id", "mfa_recovery_codes", ["user_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_mfa_recovery_codes_user_id", table_name="mfa_recovery_codes")
    op.drop_table("mfa_recovery_codes")
    op.drop_column("users", "mfa_activated_at")
    op.drop_column("users", "mfa_secret")
