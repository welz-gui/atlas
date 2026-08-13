"""Retenção de conteúdo e atendimento a titular de dado pessoal (LGPD).

Três operações, todas restritas a `org:manage` e todas com **simulação por
padrão**: `dry_run=true` mostra o que aconteceria. Para apagar de fato é preciso
pedir explicitamente — remoção de dado não acontece por clique acidental.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_project_or_404, require_permission
from app.core.config import settings
from app.core.database import get_db
from app.models.domain import User
from app.schemas.domain import (
    AnonymizationRequest,
    AnonymizationResponse,
    ContentPurgeReportResponse,
)
from app.services import privacy
from app.services.retention import (
    purge_expired_ai_interactions,
    purge_expired_job_records,
)

router = APIRouter()


def _as_response(report) -> ContentPurgeReportResponse:
    return ContentPurgeReportResponse(
        dry_run=report.dry_run,
        retention_enabled=report.retention_enabled,
        retention_days=report.retention_days,
        examined=report.examined,
        purged=report.purged,
        record_ids=report.record_ids,
    )


@router.post("/privacy/purge-ai-interactions", response_model=ContentPurgeReportResponse)
def purge_ai_interactions(
    dry_run: bool = True,
    user: User = Depends(require_permission("org:manage")),
    db: Session = Depends(get_db),
):
    """Descarta pergunta e resposta das interações vencidas (§6.6).

    A pergunta feita ao assistente pode conter dado pessoal. O que permanece é
    a proveniência: modelo, tokens, regras recuperadas, se a resposta estava
    fundamentada — sem isso, "de onde veio esta resposta" deixa de ter resposta.

    Sem `AI_INTERACTION_RETENTION_DAYS` configurado, nada é expurgado, e o
    relatório diz isso em `retention_enabled`.
    """
    report = purge_expired_ai_interactions(
        db, organization_id=user.organization_id, dry_run=dry_run
    )
    return _as_response(report)


@router.post("/privacy/purge-job-records", response_model=ContentPurgeReportResponse)
def purge_job_records(
    dry_run: bool = True,
    user: User = Depends(require_permission("org:manage")),
    db: Session = Depends(get_db),
):
    """Descarta payload e resultado dos trabalhos encerrados e vencidos.

    Só trabalho em estado terminal entra: expurgar o payload de um trabalho
    ainda enfileirado o tornaria inexecutável.
    """
    report = purge_expired_job_records(
        db, organization_id=user.organization_id, dry_run=dry_run
    )
    return _as_response(report)


@router.post(
    "/projects/{project_id}/anonymize", response_model=AnonymizationResponse
)
def anonymize_project(
    project_id: str,
    payload: AnonymizationRequest,
    user: User = Depends(require_permission("org:manage")),
    db: Session = Depends(get_db),
):
    """Atende pedido de eliminação de dado pessoal de terceiro.

    O Atlas guarda dado de quem nunca interagiu com ele — proprietário,
    contratante, responsável técnico. Este endpoint **redige** esses campos e
    preserva o registro: análises e versões são append-only (I5, I6), e apagá-las
    destruiria a prova de um ato técnico que continua produzindo efeito.

    Não decide se o pedido procede — isso é avaliação jurídica, feita por gente.
    A razão informada é o registro dessa decisão, e fica no empreendimento.
    """
    project = get_project_or_404(db, project_id, user)
    report = privacy.anonymize_project(
        db, project, reason=payload.reason, dry_run=payload.dry_run
    )
    return AnonymizationResponse(
        project_id=report.project_id,
        dry_run=report.dry_run,
        already_anonymized=report.already_anonymized,
        fields_cleared=report.fields_cleared,
        anonymized_at=report.anonymized_at,
    )
