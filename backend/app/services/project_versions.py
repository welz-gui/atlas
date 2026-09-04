"""Criação e promoção de versões de projeto (§3.2).

Versões são imutáveis. Alterar um parâmetro nunca sobrescreve a versão atual:
cria-se uma nova, com autor e motivo. É o que garante que orçamento,
quantitativos e cronograma possam referenciar uma linha de base estável
(§14.15 — nenhuma alteração silenciosa).
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models.domain import Project, ProjectVersion, ProjectVersionState, User
from app.schemas.domain import ProjectParameters

#: Campos que compõem a fotografia da versão.
VERSION_FIELDS = (
    "zone",
    "building_type",
    "lot_area",
    "built_area",
    "floors",
    "front_setback",
    "side_setback",
    "rear_setback",
    "permeability_rate",
    "parking_spaces",
)


def version_content_hash(parameters: ProjectParameters) -> str:
    values = parameters.model_dump()
    canonical = json.dumps(
        {k: values.get(k) for k in sorted(VERSION_FIELDS)},
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def create_version(
    db: Session,
    project: Project,
    parameters: ProjectParameters,
    user: Optional[User] = None,
    state: str = ProjectVersionState.ESTUDO_PRELIMINAR,
    change_reason: Optional[str] = None,
    change_origin: str = "cadastro_manual",
    commit: bool = True,
) -> ProjectVersion:
    """Cria a próxima versão do projeto a partir de `parameters`."""
    previous = project.current_version
    next_number = (previous.version_number + 1) if previous else 1

    params_dict = parameters.model_dump()
    payload = {field: params_dict.get(field) for field in VERSION_FIELDS}

    version = ProjectVersion(
        organization_id=project.organization_id,
        project_id=project.id,
        version_number=next_number,
        state=state,
        change_reason=change_reason,
        change_origin=change_origin,
        content_hash=version_content_hash(parameters),
        created_by_id=user.id if user else None,
        # Numéricos: None é significativo (não informado) e vai como está.
        lot_area=payload["lot_area"],
        built_area=payload["built_area"],
        floors=payload["floors"],
        front_setback=payload["front_setback"],
        side_setback=payload["side_setback"],
        rear_setback=payload["rear_setback"],
        permeability_rate=payload["permeability_rate"],
        parking_spaces=payload["parking_spaces"],
    )
    # Classificatórios têm default no modelo; só sobrescrevemos se informados.
    if payload.get("zone"):
        version.zone = payload["zone"]
    if payload.get("building_type"):
        version.building_type = payload["building_type"]

    db.add(version)
    if commit:
        db.commit()
        db.refresh(version)
    else:
        db.flush()
    return version


def derive_next_version(
    db: Session,
    project: Project,
    updates: ProjectParameters,
    user: Optional[User] = None,
    change_reason: Optional[str] = None,
    change_origin: str = "cadastro_manual",
    state: Optional[str] = None,
) -> ProjectVersion:
    """Cria uma versão nova copiando a atual e aplicando `updates`.

    `updates` só precisa conter o que mudou; o restante é herdado.
    """
    current = project.current_version
    base: Dict[str, Any] = (
        {field: getattr(current, field) for field in VERSION_FIELDS} if current else {}
    )
    base.update({k: v for k, v in updates.model_dump(exclude_unset=True).items() if k in VERSION_FIELDS})
    new_params = ProjectParameters.model_validate(base)

    return create_version(
        db,
        project,
        new_params,
        user=user,
        state=state or (current.state if current else ProjectVersionState.ESTUDO_PRELIMINAR),
        change_reason=change_reason,
        change_origin=change_origin,
    )


def set_official_baseline(
    db: Session, project: Project, version: ProjectVersion, user: Optional[User] = None
) -> ProjectVersion:
    """Elege uma versão aprovada como linha de base oficial (§3.2).

    Só uma versão `aprovada` pode ser linha de base — é o ato do órgão público
    que confere esse status, não uma escolha livre do usuário. A marcação é
    exclusiva: promover uma versão desmarca a anterior.
    """
    if version.state != ProjectVersionState.APROVADA:
        raise ValueError(
            "Somente uma versão no estado 'aprovada' pode ser eleita linha de base "
            f"oficial. Estado atual: '{version.state}'."
        )

    for other in project.versions:
        if other.id != version.id and other.is_official_baseline:
            other.is_official_baseline = False

    version.is_official_baseline = True
    version.baseline_marked_at = datetime.utcnow()
    db.commit()
    db.refresh(version)
    return version
