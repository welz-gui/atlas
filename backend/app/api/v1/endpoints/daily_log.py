"""Diário de obra, com escopo de organização."""

from typing import List

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_project_or_404, require_permission, tenant_query
from app.core.database import get_db
from app.models.domain import DailyLog, User
from app.schemas.domain import DailyLogCreate, DailyLogResponse

router = APIRouter()


@router.get("/projects/{project_id}/daily-logs", response_model=List[DailyLogResponse])
def list_project_daily_logs(
    project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    get_project_or_404(db, project_id, user)
    return (
        tenant_query(db, DailyLog, user)
        .filter(DailyLog.project_id == project_id)
        .order_by(DailyLog.date.desc())
        .all()
    )


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

    log = DailyLog(
        organization_id=user.organization_id,
        project_id=project_id,
        created_by_id=user.id,
        **payload.model_dump(),
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log
