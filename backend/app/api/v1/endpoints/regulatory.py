from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.models.domain import Project, ValidationRecord
from app.schemas.domain import RegulatoryAnalysisReport, ValidationRecordResponse
from app.services.regulatory_engine import RegulatoryEngine
from app.services.pdf_report_generator import RegulatoryReportGenerator

router = APIRouter()

@router.post("/projects/{project_id}/evaluate", response_model=RegulatoryAnalysisReport)
def evaluate_project_rules(project_id: str, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    records = RegulatoryEngine.evaluate_project(db, project)
    
    conforme = sum(1 for r in records if r.status == "conforme")
    nao_conforme = sum(1 for r in records if r.status == "nao_conforme")
    atencao = sum(1 for r in records if r.status == "atencao")
    nao_verificavel = sum(1 for r in records if r.status == "nao_verificavel")
    
    return RegulatoryAnalysisReport(
        project_id=project.id,
        total_checks=len(records),
        conforme_count=conforme,
        nao_conforme_count=nao_conforme,
        atencao_count=atencao,
        nao_verificavel_count=nao_verificavel,
        results=[ValidationRecordResponse.model_validate(r) for r in records]
    )

@router.get("/projects/{project_id}/validations", response_model=List[ValidationRecordResponse])
def get_project_validations(project_id: str, db: Session = Depends(get_db)):
    records = db.query(ValidationRecord).filter(ValidationRecord.project_id == project_id).all()
    return records

@router.get("/projects/{project_id}/report/pdf")
def generate_regulatory_pdf_report(project_id: str, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    records = RegulatoryEngine.evaluate_project(db, project)
    
    project_dict = {
        "id": project.id,
        "name": project.name,
        "city_name": project.city_name,
        "zone": project.zone,
        "lot_area": project.lot_area,
        "built_area": project.built_area,
        "front_setback": project.front_setback,
        "rear_setback": project.rear_setback,
        "occupancy_rate": project.occupancy_rate,
        "permeability_rate": project.permeability_rate
    }
    
    validations_list = [
        {
            "rule_title": r.rule_title,
            "expected_value": r.expected_value,
            "actual_value": r.actual_value,
            "status": r.status,
            "source_citation": r.source_citation
        }
        for r in records
    ]

    pdf_bytes = RegulatoryReportGenerator.generate_pdf(project_dict, validations_list)
    filename = f"Laudo_Conformidade_{project.name.replace(' ', '_')}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename={filename}"}
    )
