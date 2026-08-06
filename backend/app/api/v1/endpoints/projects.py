from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.models.domain import Organization, Project
from app.schemas.domain import (
    OrganizationCreate, OrganizationResponse,
    ProjectCreate, ProjectResponse, ProjectUpdate
)
from app.services.regulatory_engine import RegulatoryEngine

router = APIRouter()

# --- Organizations ---
@router.post("/organizations", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
def create_organization(org: OrganizationCreate, db: Session = Depends(get_db)):
    db_org = Organization(name=org.name, document_number=org.document_number)
    db.add(db_org)
    db.commit()
    db.refresh(db_org)
    return db_org

@router.get("/organizations", response_model=List[OrganizationResponse])
def list_organizations(db: Session = Depends(get_db)):
    return db.query(Organization).all()

# --- Projects ---
@router.post("/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(project: ProjectCreate, db: Session = Depends(get_db)):
    org = db.query(Organization).filter(Organization.id == project.organization_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
        
    db_project = Project(**project.model_dump())
    db.add(db_project)
    db.commit()
    db.refresh(db_project)

    # Análise inicial. Cria um AnalysisRun; não sobrescreve nada.
    RegulatoryEngine.evaluate_project(db, db_project, trigger="project_created")
    db.refresh(db_project)

    return db_project

@router.get("/projects", response_model=List[ProjectResponse])
def list_projects(organization_id: str = None, db: Session = Depends(get_db)):
    query = db.query(Project)
    if organization_id:
        query = query.filter(Project.organization_id == organization_id)
    return query.all()

@router.get("/projects/{project_id}", response_model=ProjectResponse)
def get_project(project_id: str, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project

@router.patch("/projects/{project_id}", response_model=ProjectResponse)
def update_project(project_id: str, project_update: ProjectUpdate, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    update_data = project_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(project, key, value)
        
    db.commit()

    # Nova análise a cada alteração de parâmetro; o histórico é preservado.
    RegulatoryEngine.evaluate_project(db, project, trigger="project_updated")
    db.refresh(project)

    return project
