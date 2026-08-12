"""Métricas do §11 em endpoint próprio (item D5 da Fase D).

Antes disto, responder "o Portão 0 → 1 foi atingido?" exigia rodar script na
máquina de alguém e ler a saída no terminal. Régua que só existe em memória é
régua que se ajusta ao resultado obtido.

O que este módulo **não** faz: não estima, não completa lacuna com zero e não
converte token em dinheiro. Ver `app.services.metrics`.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.database import get_db
from app.models.domain import User
from app.schemas.domain import (
    AIMetrics,
    ApprovalMetrics,
    GateCriterion,
    GateStatus,
    MetricsResponse,
)
from app.services import metrics as metrics_service

router = APIRouter()

#: Limiares propostos para o Portão 0 → 1 (docs/ROADMAP.md). São **proposta**:
#: o §10 do plano fala em "taxa mínima de previsão" sem fixar número. Ficam
#: aqui, em um lugar só, para que revisá-los seja uma linha e não uma caçada.
GATE_0_TO_1 = (
    ("falsos_negativos_criticos", "critical_false_negatives", 0.0, "<="),
    ("recall_de_bloqueios", "blocking_recall_percent", 80.0, ">="),
    ("regras_publicadas", "catalog_publishable_rules", 15.0, ">="),
    ("projetos_concluidos", "projects", 5.0, ">="),
)

_COMPARISONS = {
    ">=": lambda measured, threshold: measured >= threshold,
    "<=": lambda measured, threshold: measured <= threshold,
}


def _evaluate_gate(approval: dict) -> GateStatus:
    criteria = []
    for name, field, threshold, comparison in GATE_0_TO_1:
        measured: Optional[float] = approval.get(field)
        met = (
            _COMPARISONS[comparison](measured, threshold)
            if measured is not None
            else None
        )
        criteria.append(
            GateCriterion(
                name=name,
                measured=measured,
                threshold=threshold,
                comparison=comparison,
                met=met,
            )
        )

    # Portão não se atravessa por falta de dado: basta um critério sem medição
    # para que o veredicto seja "não sei", e não "sim".
    if any(c.met is None for c in criteria):
        overall = None
    else:
        overall = all(c.met for c in criteria)

    return GateStatus(criteria=criteria, overall=overall)


@router.get("/metrics", response_model=MetricsResponse)
def read_metrics(
    user: User = Depends(require_permission("metrics:read")),
    db: Session = Depends(get_db),
):
    """Métricas de aprovação e de IA da própria organização (§11).

    Restrito a quem responde pelo número — `owner`, `admin` e `validator`. O
    recorte é sempre a organização do usuário; não há parâmetro para consultar
    outra (I12).
    """
    approval = metrics_service.approval_metrics(db, user.organization_id)
    ai = metrics_service.ai_metrics(db, user.organization_id)

    return MetricsResponse(
        organization_id=user.organization_id,
        generated_at=datetime.utcnow(),
        approval=ApprovalMetrics(**approval),
        ai=AIMetrics(**ai),
        gate_0_to_1=_evaluate_gate(approval),
    )
