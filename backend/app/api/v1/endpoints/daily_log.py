"""Diário de obra, com escopo de organização.

A criação é idempotente por `client_token` (§3.7): o aplicativo de campo grava
offline e reenvia quando a rede volta, e uma resposta perdida no caminho não
pode produzir dois diários para o mesmo dia.
"""

from typing import List

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
from app.services import daily_log_signature
from app.models.domain import DailyLog, DailyLogState, User
from app.schemas.domain import DailyLogCreate, DailyLogResponse

router = APIRouter()


def _with_signature(log: DailyLog) -> DailyLogResponse:
    """Monta a resposta recalculando a validade da assinatura.

    A conferência é feita na leitura, e não guardada: um valor gravado diria
    apenas o que era verdade quando foi gravado. Recalcular responde agora.
    """
    resposta = DailyLogResponse.model_validate(log)
    resposta.signature_valid = daily_log_signature.signature_is_valid(log)
    return resposta


@router.get("/projects/{project_id}/daily-logs", response_model=List[DailyLogResponse])
def list_project_daily_logs(
    project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    get_project_or_404(db, project_id, user)
    registros = (
        tenant_query(db, DailyLog, user)
        .filter(DailyLog.project_id == project_id)
        .order_by(DailyLog.date.desc())
        .all()
    )
    return [_with_signature(log) for log in registros]


@router.post(
    "/projects/{project_id}/daily-logs",
    response_model=DailyLogResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_daily_log(
    project_id: str,
    payload: DailyLogCreate,
    user: User = Depends(require_permission("field:write")),
    db: Session = Depends(get_db),
):
    get_project_or_404(db, project_id, user)

    if payload.client_token:
        existente = (
            tenant_query(db, DailyLog, user)
            .filter(
                DailyLog.project_id == project_id,
                DailyLog.client_token == payload.client_token,
            )
            .first()
        )
        if existente:
            # Reenvio do mesmo item da fila: devolve o registro original, com
            # 201, em vez de duplicar. O cliente não tem como distinguir
            # "não chegou" de "chegou e a resposta se perdeu".
            return _with_signature(existente)

    log = DailyLog(
        organization_id=user.organization_id,
        project_id=project_id,
        created_by_id=user.id,
        **payload.model_dump(),
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return _with_signature(log)


@router.post("/daily-logs/{log_id}/sign", response_model=DailyLogResponse)
def sign_daily_log(
    log_id: str,
    user: User = Depends(require_permission("field:write")),
    db: Session = Depends(get_db),
):
    """Assina o diário: quem, quando e sobre qual conteúdo (§8.12).

    Assinar não é mudar um rótulo. Grava a identidade de quem assinou, o
    instante, e o hash do conteúdo — sem o hash, "assinado" não distinguiria o
    texto que a pessoa leu do texto que alguém alterou depois.

    Reassinar é recusado: a assinatura vale para um conteúdo, e um segundo ato
    sobre o mesmo registro tornaria ambíguo qual deles alguém está invocando.
    """
    log = get_scoped_or_404(db, DailyLog, log_id, user, "Diário")

    if log.status == DailyLogState.ASSINADO:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Diário já assinado por {log.signed_by_name} "
                f"em {log.signed_at:%Y-%m-%d %H:%M}."
            ),
        )

    return _with_signature(daily_log_signature.sign(db, log, user))
