"""Atendimento a pedido de eliminação de dado pessoal (LGPD).

O Atlas guarda dado de pessoas que **nunca interagiram com ele**: o
proprietário do lote, o contratante, o responsável técnico. Elas podem pedir
eliminação, e a resposta não pode ser "não dá".

Também não pode ser `DELETE`. `AnalysisRun` e `ProjectVersion` são append-only
por desenho (I5, I6): é o que permite responder, daqui a três anos, qual versão
do projeto foi protocolada e o que o motor disse sobre ela. Apagar a linha
destruiria a prova de um ato técnico que aconteceu — e que continua produzindo
efeito, porque o alvará foi emitido com base nele.

O caminho é **redigir o dado pessoal e preservar o registro**. Depois da
anonimização:

- o empreendimento continua existindo, com endereço, zona e parâmetros;
- as análises continuam íntegras, com o mesmo `content_hash`;
- o nome e o documento do proprietário deixam de estar em qualquer lugar;
- fica gravado **quando** e **por quê**, porque a própria anonimização é um ato
  que precisa de trilha.

O que este módulo **não** decide: se o pedido procede. Isso é avaliação
jurídica, feita por gente, e a razão informada é o registro dessa decisão.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.domain import Project

#: Colunas de `Project` que carregam dado pessoal de terceiro. Nenhuma delas
#: participa de regra do motor: anonimizar não altera veredicto nenhum.
PERSONAL_FIELDS = (
    "owner_name",
    "owner_document",
    "contractor_name",
    "technical_responsible_name",
    "technical_responsible_registry",
)

#: O que fica no lugar. Texto, e não `NULL`, para que a diferença entre "nunca
#: foi preenchido" e "foi removido a pedido" permaneça legível.
REDACTED = "[removido a pedido do titular]"


@dataclass
class AnonymizationReport:
    project_id: str
    dry_run: bool = False
    already_anonymized: bool = False
    fields_cleared: List[str] = field(default_factory=list)
    anonymized_at: Optional[datetime] = None


def anonymize_project(
    db: Session,
    project: Project,
    reason: str,
    now: Optional[datetime] = None,
    dry_run: bool = False,
) -> AnonymizationReport:
    """Redige o dado pessoal de terceiros do empreendimento.

    Idempotente: pedir duas vezes não sobrescreve a data do primeiro
    atendimento, porque o que importa é quando o titular foi atendido.
    """
    report = AnonymizationReport(project_id=project.id, dry_run=dry_run)

    if project.anonymized_at is not None:
        report.already_anonymized = True
        report.anonymized_at = project.anonymized_at
        return report

    for name in PERSONAL_FIELDS:
        value = getattr(project, name, None)
        if value and value != REDACTED:
            report.fields_cleared.append(name)

    if dry_run:
        return report

    moment = now or datetime.utcnow()
    for name in report.fields_cleared:
        setattr(project, name, REDACTED)

    project.anonymized_at = moment
    project.anonymization_reason = reason
    report.anonymized_at = moment

    db.commit()
    return report
