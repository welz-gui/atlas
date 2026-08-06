import hashlib
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.domain import AnalysisRun, Project, ValidationRecord
from app.schemas.domain import (
    AnalysisRunDetail,
    AnalysisRunResponse,
    RegulatoryAnalysisReport,
    ValidationRecordResponse,
)
from app.services.pdf_report_generator import RegulatoryReportGenerator
from app.services.regulatory_engine import RegulatoryEngine

router = APIRouter()


def _get_project(db: Session, project_id: str) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _to_report(run: AnalysisRun) -> RegulatoryAnalysisReport:
    return RegulatoryAnalysisReport(
        project_id=run.project_id,
        analysis_run_id=run.id,
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
def evaluate_project_rules(project_id: str, db: Session = Depends(get_db)):
    """Executa o catálogo e registra uma nova análise (append-only)."""
    project = _get_project(db, project_id)
    run = RegulatoryEngine.evaluate_project(db, project, trigger="manual")
    return _to_report(run)


@router.get("/projects/{project_id}/validations", response_model=List[ValidationRecordResponse])
def get_project_validations(project_id: str, db: Session = Depends(get_db)):
    """Verificações da análise mais recente."""
    _get_project(db, project_id)
    run = RegulatoryEngine.latest_run(db, project_id)
    if not run:
        return []
    return (
        db.query(ValidationRecord)
        .filter(ValidationRecord.analysis_run_id == run.id)
        .all()
    )


@router.get("/projects/{project_id}/analysis-runs", response_model=List[AnalysisRunResponse])
def list_analysis_runs(project_id: str, db: Session = Depends(get_db)):
    """Histórico completo de análises — nada é sobrescrito (§3.5)."""
    _get_project(db, project_id)
    return (
        db.query(AnalysisRun)
        .filter(AnalysisRun.project_id == project_id)
        .order_by(AnalysisRun.created_at.desc())
        .all()
    )


@router.get("/analysis-runs/{run_id}", response_model=AnalysisRunDetail)
def get_analysis_run(run_id: str, db: Session = Depends(get_db)):
    run = db.query(AnalysisRun).filter(AnalysisRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Analysis run not found")
    return run


@router.get("/projects/{project_id}/report/pdf")
def generate_regulatory_pdf_report(
    project_id: str,
    run_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Renderiza o laudo de uma análise **já existente**.

    Este endpoint é somente leitura: ele nunca dispara uma nova avaliação. Para
    analisar o projeto, use `POST /projects/{id}/evaluate`. Informe `run_id`
    para reemitir o laudo de uma análise histórica.
    """
    project = _get_project(db, project_id)

    if run_id:
        run = (
            db.query(AnalysisRun)
            .filter(AnalysisRun.id == run_id, AnalysisRun.project_id == project_id)
            .first()
        )
        if not run:
            raise HTTPException(status_code=404, detail="Analysis run not found")
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

    project_dict = {
        "id": project.id,
        "name": project.name,
        "city_name": project.city_name,
        "state": project.state,
        "zone": project.zone,
        "lot_area": project.lot_area,
        "built_area": project.built_area,
        "floors": project.floors,
        "front_setback": project.front_setback,
        "rear_setback": project.rear_setback,
        "occupancy_rate": project.occupancy_rate,
        "permeability_rate": project.permeability_rate,
        "is_official_baseline": project.is_official_baseline,
    }

    validations = [
        {
            "rule_title": record.rule_title,
            "expected_value": record.expected_value,
            "actual_value": record.actual_value,
            "status": record.status,
            "details": record.details,
            "source_citation": record.source_citation,
            "source_is_verified": record.source_is_verified,
            "evidence_required": record.evidence_required,
        }
        for record in run.validations
    ]

    run_dict = {
        "id": run.id,
        "content_hash": run.content_hash,
        "catalog_version": run.catalog_version,
        "engine_version": run.engine_version,
        "is_publishable": run.is_publishable,
        "created_at": run.created_at,
    }

    pdf_bytes = RegulatoryReportGenerator.generate_pdf(project_dict, validations, run_dict)
    safe_name = "".join(
        c if c.isalnum() or c in "-_" else "_" for c in project.name
    )[:60] or "empreendimento"
    prefix = "USO_INTERNO_" if not run.is_publishable else ""
    filename = f"{prefix}Pre_Analise_{safe_name}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "X-Atlas-Analysis-Run": run.id,
            "X-Atlas-Content-Hash": run.content_hash or "",
            "X-Atlas-Pdf-Sha256": hashlib.sha256(pdf_bytes).hexdigest(),
            "X-Atlas-Publishable": "true" if run.is_publishable else "false",
        },
    )
