"""Trabalhos assíncronos (§6.7).

Enfileirar e acompanhar. O que a interface precisa saber deste endpoint é que
`202 Accepted` significa aceito, não concluído: o resultado chega em
`GET /jobs/{id}`. Quando não há broker configurado, o trabalho já vem
concluído na própria resposta — e com `executed_inline=true`, para que a
diferença fique visível em vez de suposta.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import (
    get_current_user,
    get_project_or_404,
    get_scoped_or_404,
    require_permission,
    tenant_query,
)
from app.core.database import get_db
from app.models.domain import Document, JobRecord, JobStatus, JobType, User
from app.schemas.domain import JobRecordResponse, JobSubmitResponse
from app.workers.queue import enqueue, get_queue

router = APIRouter()


def _submit(db: Session, response: Response, record: JobRecord) -> JobSubmitResponse:
    # Trabalho já concluído (execução inline) responde 200; o que ficou na fila
    # responde 202 — o código HTTP conta a mesma verdade que o corpo.
    response.status_code = (
        status.HTTP_200_OK if record.is_terminal else status.HTTP_202_ACCEPTED
    )
    return JobSubmitResponse(
        job=JobRecordResponse.model_validate(record),
        queue_backend=get_queue().describe(),
    )


@router.post("/projects/{project_id}/jobs/analysis", response_model=JobSubmitResponse)
def enqueue_analysis(
    project_id: str,
    response: Response,
    project_version_id: Optional[str] = None,
    user: User = Depends(require_permission("project:write")),
    db: Session = Depends(get_db),
):
    """Executa o catálogo fora do ciclo da requisição."""
    get_project_or_404(db, project_id, user)
    record = enqueue(
        db,
        JobType.ANALISE_REGULATORIA,
        payload={
            "project_id": project_id,
            "project_version_id": project_version_id,
            "trigger": "assincrono",
        },
        user=user,
        project_id=project_id,
    )
    return _submit(db, response, record)


@router.post("/projects/{project_id}/jobs/report", response_model=JobSubmitResponse)
def enqueue_report(
    project_id: str,
    response: Response,
    analysis_run_id: Optional[str] = None,
    user: User = Depends(require_permission("project:read")),
    db: Session = Depends(get_db),
):
    """Emite o laudo em PDF e o guarda no storage."""
    get_project_or_404(db, project_id, user)
    record = enqueue(
        db,
        JobType.GERACAO_LAUDO,
        payload={"project_id": project_id, "analysis_run_id": analysis_run_id},
        user=user,
        project_id=project_id,
    )
    return _submit(db, response, record)


@router.post("/documents/{document_id}/jobs/extract", response_model=JobSubmitResponse)
def enqueue_extraction(
    document_id: str,
    response: Response,
    user: User = Depends(require_permission("document:read")),
    db: Session = Depends(get_db),
):
    """Extrai parâmetros do documento sem prender a requisição."""
    document = get_scoped_or_404(db, Document, document_id, user, "Documento")
    record = enqueue(
        db,
        JobType.EXTRACAO_DOCUMENTO,
        payload={"document_id": document.id},
        user=user,
        project_id=document.project_id,
    )
    return _submit(db, response, record)


@router.post("/jobs/retention-purge", response_model=JobSubmitResponse)
def enqueue_retention_purge(
    response: Response,
    dry_run: bool = True,
    user: User = Depends(require_permission("org:manage")),
    db: Session = Depends(get_db),
):
    """Aplica a política de retenção da organização (§6.6) como trabalho."""
    record = enqueue(
        db,
        JobType.EXPURGO_RETENCAO,
        payload={"dry_run": dry_run},
        user=user,
    )
    return _submit(db, response, record)


@router.post("/catalog/jobs/discovery", response_model=JobSubmitResponse)
def enqueue_regulatory_discovery(
    response: Response,
    jurisdiction: str = "BR-RS-4311403",
    project_id: Optional[str] = None,
    user: User = Depends(require_permission("catalog:validate")),
    db: Session = Depends(get_db),
):
    """Busca normas em fontes oficiais, sem criar ou publicar regras."""
    from app.regulatory.discovery import SOURCES
    from app.regulatory.jurisdiction import jurisdiction_chain

    project = get_project_or_404(db, project_id, user) if project_id else None
    target_jurisdiction = project.city_ibge if project else jurisdiction
    scopes = jurisdiction_chain(target_jurisdiction)
    municipal_scope_missing = len(scopes) == 3 and target_jurisdiction not in SOURCES
    if municipal_scope_missing or not any(scope in SOURCES for scope in scopes):
        raise HTTPException(
            status_code=422,
            detail=f"Não há fontes oficiais configuradas para {target_jurisdiction} ou seus escopos superiores.",
        )
    record = enqueue(
        db,
        JobType.DESCOBERTA_REGULATORIA,
        payload={"jurisdiction": target_jurisdiction},
        user=user,
        project_id=project.id if project else None,
    )
    return _submit(db, response, record)


@router.get("/jobs", response_model=List[JobRecordResponse])
def list_jobs(
    project_id: Optional[str] = None,
    job_status: Optional[str] = None,
    limit: int = 50,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = tenant_query(db, JobRecord, user)
    if project_id:
        get_project_or_404(db, project_id, user)
        query = query.filter(JobRecord.project_id == project_id)
    if job_status:
        if job_status not in JobStatus.ALL:
            raise HTTPException(
                status_code=422,
                detail=f"Situação desconhecida. Aceitas: {', '.join(sorted(JobStatus.ALL))}.",
            )
        query = query.filter(JobRecord.status == job_status)
    return query.order_by(JobRecord.queued_at.desc()).limit(min(limit, 200)).all()


@router.get("/jobs/{job_id}", response_model=JobRecordResponse)
def get_job(
    job_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_scoped_or_404(db, JobRecord, job_id, user, "Trabalho")
