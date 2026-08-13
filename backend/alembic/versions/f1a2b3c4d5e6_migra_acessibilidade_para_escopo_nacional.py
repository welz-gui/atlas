"""migra acessibilidade para escopo nacional

Revision ID: f1a2b3c4d5e6
Revises: e8f2a1c60d47
"""

from typing import Sequence, Union

from alembic import op


revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "e8f2a1c60d47"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE regulatory_rules
        SET jurisdiction = 'BR',
            rule_key = 'brasil_acessibilidade_edificacoes',
            title = 'Acessibilidade em edificações e rota acessível',
            source_document_label = 'Lei Federal nº 10.098/2000',
            notes = 'Regra nacional; normas técnicas vigentes devem ser confirmadas pelo validador.'
        WHERE jurisdiction = 'BR-RS-4311403'
          AND rule_key = 'lajeado_acessibilidade_nbr9050'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE regulatory_rules
        SET jurisdiction = 'BR-RS-4311403',
            rule_key = 'lajeado_acessibilidade_nbr9050',
            title = 'Conformidade NBR 9050 — Acessibilidade e Rota Acessível',
            source_document_label = 'ABNT NBR 9050'
        WHERE jurisdiction = 'BR'
          AND rule_key = 'brasil_acessibilidade_edificacoes'
        """
    )
