"""Empreendimentos e versões de projeto (§8.2, §3.2)."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_project_or_404, require_permission, tenant_query
from app.core.database import get_db
from app.models.domain import Organization, Project, ProjectVersion, ProjectVersionState, User
from app.schemas.domain import (
    OrganizationResponse,
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
    ProjectVersionCreate,
    ProjectVersionResponse,
    VersionStateChange,
)
from app.services import project_versions
from app.services.regulatory_engine import RegulatoryEngine

router = APIRouter()


@router.get("/organizations", response_model=List[OrganizationResponse])
def list_organizations(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Somente a organização do usuário — não há listagem global."""
    return db.query(Organization).filter(Organization.id == user.organization_id).all()


# --- Empreendimentos --------------------------------------------------------

@router.post("/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    user: User = Depends(require_permission("project:write")),
    db: Session = Depends(get_db),
):
    identity = payload.model_dump(
        exclude={
            "zone", "building_type", "lot_area", "built_area", "floors",
            "front_setback", "side_setback", "rear_setback",
            "permeability_rate", "parking_spaces",
        }
    )
    project = Project(
        organization_id=user.organization_id, created_by_id=user.id, **identity
    )
    db.add(project)
    db.flush()

    project_versions.create_version(
        db,
        project,
        payload.model_dump(),
        user=user,
        change_reason="Cadastro inicial do empreendimento.",
        commit=False,
    )
    db.commit()
    db.refresh(project)

    RegulatoryEngine.evaluate_project(db, project, trigger="project_created", user=user)
    db.refresh(project)
    return project


@router.get("/projects", response_model=List[ProjectResponse])
def list_projects(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return tenant_query(db, Project, user).all()


@router.get("/projects/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    return get_project_or_404(db, project_id, user)


@router.patch("/projects/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: str,
    payload: ProjectUpdate,
    user: User = Depends(require_permission("project:write")),
    db: Session = Depends(get_db),
):
    """Atualiza a identidade do empreendimento.

    Parâmetros urbanísticos **não** são editáveis aqui — eles pertencem a uma
    versão. Use `POST /projects/{id}/versions`.
    """
    project = get_project_or_404(db, project_id, user)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(project, key, value)
    db.commit()

    # Re-evaluate regulatory rules on project parameter change
    RegulatoryEngine.evaluate_project(db, project)
    db.refresh(project)
    return project


# --- Versões ----------------------------------------------------------------

@router.get("/projects/{project_id}/versions", response_model=List[ProjectVersionResponse])
def list_versions(
    project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    project = get_project_or_404(db, project_id, user)
    return sorted(project.versions, key=lambda v: v.version_number, reverse=True)


@router.post(
    "/projects/{project_id}/versions",
    response_model=ProjectVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_version(
    project_id: str,
    payload: ProjectVersionCreate,
    user: User = Depends(require_permission("project:write")),
    db: Session = Depends(get_db),
):
    """Cria uma versão nova a partir da vigente, aplicando as alterações.

    A versão anterior permanece intacta — é o que sustenta a linha de base.
    """
    project = get_project_or_404(db, project_id, user)

    if payload.state and payload.state not in ProjectVersionState.ALL:
        raise HTTPException(
            status_code=422,
            detail=f"Estado inválido. Válidos: {', '.join(sorted(ProjectVersionState.ALL))}",
        )

    updates = payload.model_dump(exclude_unset=True, exclude={"change_reason", "state"})
    version = project_versions.derive_next_version(
        db,
        project,
        updates,
        user=user,
        change_reason=payload.change_reason,
        state=payload.state,
    )

    db.refresh(project)
    RegulatoryEngine.evaluate_project(
        db, project, trigger="version_created", user=user, version=version
    )
    db.refresh(version)
    return version


@router.patch(
    "/projects/{project_id}/versions/{version_id}/state",
    response_model=ProjectVersionResponse,
)
def change_version_state(
    project_id: str,
    version_id: str,
    payload: VersionStateChange,
    user: User = Depends(require_permission("project:write")),
    db: Session = Depends(get_db),
):
    """Move a versão pelo ciclo do §3.2 (protocolada, notificada, aprovada...)."""
    project = get_project_or_404(db, project_id, user)
    version = next((v for v in project.versions if v.id == version_id), None)
    if not version:
        raise HTTPException(status_code=404, detail="Versão não encontrada.")

    if payload.state not in ProjectVersionState.ALL:
        raise HTTPException(
            status_code=422,
            detail=f"Estado inválido. Válidos: {', '.join(sorted(ProjectVersionState.ALL))}",
        )

    version.state = payload.state
    if payload.change_reason:
        version.change_reason = payload.change_reason
    db.commit()
    db.refresh(version)
    return version


@router.post(
    "/projects/{project_id}/versions/{version_id}/baseline",
    response_model=ProjectVersionResponse,
)
def mark_official_baseline(
    project_id: str,
    version_id: str,
    user: User = Depends(require_permission("project:baseline")),
    db: Session = Depends(get_db),
):
    """Elege a versão como linha de base oficial (§3.2).

    Exige que a versão esteja `aprovada`: é a aprovação pelo órgão público que
    cria a linha de base, não uma escolha livre do usuário.
    """
    project = get_project_or_404(db, project_id, user)
    version = next((v for v in project.versions if v.id == version_id), None)
    if not version:
        raise HTTPException(status_code=404, detail="Versão não encontrada.")

    try:
        return project_versions.set_official_baseline(db, project, version, user=user)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
