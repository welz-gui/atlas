from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_project_or_404, require_permission, tenant_query
from app.core.database import get_db
from app.models.domain import AnalysisRun, User, ValidationRecord
from app.schemas.domain import (
    AnalysisRunDetail,
    AnalysisRunResponse,
    RegulatoryAnalysisReport,
    ValidationRecordResponse,
)
from app.services.regulatory_engine import RegulatoryEngine
from app.services.report_builder import build_report

router = APIRouter()


def _to_report(run: AnalysisRun) -> RegulatoryAnalysisReport:
    return RegulatoryAnalysisReport(
        project_id=run.project_id,
        analysis_run_id=run.id,
        project_version_number=run.project_version_number,
        catalog_version=run.catalog_version,
        engine_version=run.engine_version,
        total_checks=run.total_checks,
        conforme_count=run.conforme_count,
        nao_conforme_count=run.nao_conforme_count,
        atencao_count=run.atencao_count,
        nao_verificavel_count=run.nao_verificavel_count,
        is_publishable=run.is_publishable,
        content_hash=run.content_hash,
        results=[ValidationRecordResponse.model_validate(r) for r in run.validations],
    )


@router.post("/projects/{project_id}/evaluate", response_model=RegulatoryAnalysisReport)
def evaluate_project_rules(
    project_id: str,
    user: User = Depends(require_permission("project:write")),
    db: Session = Depends(get_db),
):
    """Executa o catálogo sobre a versão vigente e registra uma nova análise."""
    project = get_project_or_404(db, project_id, user)
    try:
        run = RegulatoryEngine.evaluate_project(db, project, trigger="manual", user=user)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return _to_report(run)


@router.get(
    "/projects/{project_id}/validations", response_model=List[ValidationRecordResponse]
)
def get_project_validations(
    project_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Verificações da análise mais recente."""
    get_project_or_404(db, project_id, user)
    run = RegulatoryEngine.latest_run(db, project_id)
    if not run:
        return []
    return (
        tenant_query(db, ValidationRecord, user)
        .filter(ValidationRecord.analysis_run_id == run.id)
        .all()
    )


@router.get(
    "/projects/{project_id}/analysis-runs", response_model=List[AnalysisRunResponse]
)
def list_analysis_runs(
    project_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Histórico completo de análises — nada é sobrescrito (§3.5)."""
    get_project_or_404(db, project_id, user)
    return (
        tenant_query(db, AnalysisRun, user)
        .filter(AnalysisRun.project_id == project_id)
        .order_by(AnalysisRun.created_at.desc())
        .all()
    )


@router.get("/analysis-runs/{run_id}", response_model=AnalysisRunDetail)
def get_analysis_run(
    run_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    run = tenant_query(db, AnalysisRun, user).filter(AnalysisRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Análise não encontrada.")
    return run


@router.get("/projects/{project_id}/report/pdf")
def generate_regulatory_pdf_report(
    project_id: str,
    run_id: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Renderiza o laudo de uma análise **já existente**.

    Somente leitura: nunca dispara uma nova avaliação. Para analisar, use
    `POST /projects/{id}/evaluate`. Informe `run_id` para reemitir o laudo de
    uma análise histórica.
    """
    project = get_project_or_404(db, project_id, user)

    if run_id:
        run = (
            tenant_query(db, AnalysisRun, user)
            .filter(AnalysisRun.id == run_id, AnalysisRun.project_id == project_id)
            .first()
        )
        if not run:
            raise HTTPException(status_code=404, detail="Análise não encontrada.")
    else:
        run = RegulatoryEngine.latest_run(db, project_id)

    if not run:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Nenhuma análise registrada para este empreendimento. "
                "Execute POST /projects/{project_id}/evaluate antes de emitir o laudo."
            ),
        )

    # A montagem vive em `report_builder` para que o worker (§6.7) emita
    # exatamente o mesmo documento que este endpoint.
    pdf_bytes, filename, pdf_sha256 = build_report(project, run)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "X-Atlas-Analysis-Run": run.id,
            "X-Atlas-Content-Hash": run.content_hash or "",
            "X-Atlas-Pdf-Sha256": pdf_sha256,
            "X-Atlas-Publishable": "true" if run.is_publishable else "false",
        },
    )
