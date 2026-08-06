"""Tramitação municipal (§8.5).

É aqui que a tese do produto (§2) fecha o laço: cada exigência real do órgão
pode ser vinculada à regra do catálogo que deveria tê-la antecipado, o que
permite medir o recall de bloqueios (§11) em vez de supô-lo.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import (
    get_current_user,
    get_project_or_404,
    get_scoped_or_404,
    require_permission,
    tenant_query,
)
from app.core.database import get_db
from app.models.domain import (
    ProtocolEvent,
    ProtocolProcess,
    ProtocolRequirement,
    ProtocolStatus,
    RequirementStatus,
    User,
)
from app.schemas.domain import (
    PredictionAccuracy,
    ProtocolProcessCreate,
    ProtocolProcessResponse,
    ProtocolRequirementCreate,
    ProtocolRequirementResponse,
    ProtocolRequirementUpdate,
    ProtocolStatusChange,
)
from app.services.regulatory_engine import RegulatoryEngine

router = APIRouter()


def _record_event(
    db: Session,
    process: ProtocolProcess,
    event_type: str,
    user: User,
    description: Optional[str] = None,
    from_status: Optional[str] = None,
    to_status: Optional[str] = None,
) -> None:
    db.add(
        ProtocolEvent(
            organization_id=process.organization_id,
            process_id=process.id,
            event_type=event_type,
            from_status=from_status,
            to_status=to_status,
            description=description,
            actor_id=user.id,
            actor_name=user.name,
        )
    )


@router.get("/projects/{project_id}/protocols", response_model=List[ProtocolProcessResponse])
def list_protocols(
    project_id: str,
    user: User = Depends(require_permission("protocol:read")),
    db: Session = Depends(get_db),
):
    get_project_or_404(db, project_id, user)
    return (
        tenant_query(db, ProtocolProcess, user)
        .filter(ProtocolProcess.project_id == project_id)
        .order_by(ProtocolProcess.created_at.desc())
        .all()
    )


@router.post(
    "/projects/{project_id}/protocols",
    response_model=ProtocolProcessResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_protocol(
    project_id: str,
    payload: ProtocolProcessCreate,
    user: User = Depends(require_permission("protocol:write")),
    db: Session = Depends(get_db),
):
    project = get_project_or_404(db, project_id, user)

    version_id = payload.project_version_id
    if version_id and not any(v.id == version_id for v in project.versions):
        raise HTTPException(
            status_code=422, detail="A versão informada não pertence a este empreendimento."
        )
    if not version_id and project.current_version:
        version_id = project.current_version.id

    process = ProtocolProcess(
        organization_id=user.organization_id,
        project_id=project.id,
        project_version_id=version_id,
        protocol_number=payload.protocol_number,
        agency=payload.agency,
        process_type=payload.process_type,
        submitted_at=payload.submitted_at,
        notes=payload.notes,
        created_by_id=user.id,
    )
    db.add(process)
    db.flush()

    _record_event(
        db,
        process,
        "protocolo_registrado",
        user,
        description=f"Protocolo {payload.protocol_number} registrado em {payload.agency}.",
        to_status=ProtocolStatus.PROTOCOLADO,
    )
    project.licensing_status = ProtocolStatus.PROTOCOLADO
    db.commit()
    db.refresh(process)
    return process


@router.get("/protocols/{process_id}", response_model=ProtocolProcessResponse)
def get_protocol(
    process_id: str,
    user: User = Depends(require_permission("protocol:read")),
    db: Session = Depends(get_db),
):
    return get_scoped_or_404(db, ProtocolProcess, process_id, user, "Processo")


@router.patch("/protocols/{process_id}/status", response_model=ProtocolProcessResponse)
def change_protocol_status(
    process_id: str,
    payload: ProtocolStatusChange,
    user: User = Depends(require_permission("protocol:write")),
    db: Session = Depends(get_db),
):
    process = get_scoped_or_404(db, ProtocolProcess, process_id, user, "Processo")

    if payload.status not in ProtocolStatus.ALL:
        raise HTTPException(
            status_code=422,
            detail=f"Situação inválida. Válidas: {', '.join(sorted(ProtocolStatus.ALL))}",
        )
    if process.status in ProtocolStatus.TERMINAL:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"O processo está em situação terminal ('{process.status}') e não "
                "admite nova transição. Registre um novo protocolo."
            ),
        )

    previous = process.status
    process.status = payload.status
    if payload.decided_at:
        process.decided_at = payload.decided_at

    _record_event(
        db,
        process,
        "mudanca_situacao",
        user,
        description=payload.description,
        from_status=previous,
        to_status=payload.status,
    )

    project = get_project_or_404(db, process.project_id, user)
    project.licensing_status = payload.status

    db.commit()
    db.refresh(process)
    return process


# --- Exigências e notificações ----------------------------------------------

@router.post(
    "/protocols/{process_id}/requirements",
    response_model=ProtocolRequirementResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_requirement(
    process_id: str,
    payload: ProtocolRequirementCreate,
    user: User = Depends(require_permission("protocol:write")),
    db: Session = Depends(get_db),
):
    """Registra uma exigência do órgão.

    Se a exigência for vinculada a uma regra do catálogo, o Atlas verifica se a
    análise mais recente já havia apontado aquele item como não conforme — é o
    dado que alimenta a métrica de recall de bloqueios (§11).
    """
    process = get_scoped_or_404(db, ProtocolProcess, process_id, user, "Processo")

    was_predicted = None
    if payload.linked_rule_key:
        run = RegulatoryEngine.latest_run(db, process.project_id)
        if run:
            match = next(
                (v for v in run.validations if v.rule_id == payload.linked_rule_key), None
            )
            if match is not None:
                was_predicted = match.status in ("nao_conforme", "atencao")

    next_sequence = len(process.requirements) + 1
    requirement = ProtocolRequirement(
        organization_id=user.organization_id,
        process_id=process.id,
        sequence=next_sequence,
        description=payload.description,
        origin=payload.origin,
        raised_at=payload.raised_at,
        due_date=payload.due_date,
        linked_rule_key=payload.linked_rule_key,
        was_predicted=was_predicted,
    )
    db.add(requirement)

    _record_event(
        db,
        process,
        "exigencia_registrada",
        user,
        description=f"Exigência {next_sequence}: {payload.description[:120]}",
    )

    # Uma exigência aberta muda a situação do processo — a menos que já esteja
    # em correção ou encerrado.
    if process.status not in ProtocolStatus.TERMINAL | {ProtocolStatus.EM_CORRECAO}:
        process.status = ProtocolStatus.NOTIFICADO

    db.commit()
    db.refresh(requirement)
    return requirement


@router.get(
    "/protocols/{process_id}/requirements",
    response_model=List[ProtocolRequirementResponse],
)
def list_requirements(
    process_id: str,
    user: User = Depends(require_permission("protocol:read")),
    db: Session = Depends(get_db),
):
    process = get_scoped_or_404(db, ProtocolProcess, process_id, user, "Processo")
    return sorted(process.requirements, key=lambda r: r.sequence)


@router.patch(
    "/requirements/{requirement_id}", response_model=ProtocolRequirementResponse
)
def update_requirement(
    requirement_id: str,
    payload: ProtocolRequirementUpdate,
    user: User = Depends(require_permission("protocol:write")),
    db: Session = Depends(get_db),
):
    requirement = get_scoped_or_404(
        db, ProtocolRequirement, requirement_id, user, "Exigência"
    )

    if payload.status and payload.status not in RequirementStatus.ALL:
        raise HTTPException(
            status_code=422,
            detail=f"Situação inválida. Válidas: {', '.join(sorted(RequirementStatus.ALL))}",
        )

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(requirement, key, value)

    db.commit()
    db.refresh(requirement)
    return requirement


# --- Métrica de acerto -------------------------------------------------------

@router.get("/projects/{project_id}/prediction-accuracy", response_model=PredictionAccuracy)
def prediction_accuracy(
    project_id: str,
    user: User = Depends(require_permission("protocol:read")),
    db: Session = Depends(get_db),
):
    """Recall de bloqueios do empreendimento (§11 — métricas de aprovação)."""
    get_project_or_404(db, project_id, user)

    processes = (
        tenant_query(db, ProtocolProcess, user)
        .filter(ProtocolProcess.project_id == project_id)
        .all()
    )
    requirements = [r for process in processes for r in process.requirements]

    linked = [r for r in requirements if r.linked_rule_key]
    predicted = sum(1 for r in linked if r.was_predicted)
    not_predicted = sum(1 for r in linked if r.was_predicted is False)

    recall = round(predicted / len(linked) * 100, 1) if linked else None

    return PredictionAccuracy(
        total_requirements=len(requirements),
        linked_to_rules=len(linked),
        predicted=predicted,
        not_predicted=not_predicted,
        recall_percent=recall,
    )
