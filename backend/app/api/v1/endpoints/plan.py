"""EAP e quadro de tarefas, com escopo de organização."""

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
from app.models.domain import EAPItem, TaskItem, User
from app.schemas.domain import (
    EAPItemCreate,
    EAPItemResponse,
    TaskItemCreate,
    TaskItemResponse,
    TaskItemUpdate,
)

router = APIRouter()


# --- EAP --------------------------------------------------------------------

@router.get("/projects/{project_id}/eap", response_model=List[EAPItemResponse])
def list_project_eap(
    project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    get_project_or_404(db, project_id, user)
    return (
        tenant_query(db, EAPItem, user)
        .filter(EAPItem.project_id == project_id)
        .order_by(EAPItem.code)
        .all()
    )


@router.post(
    "/projects/{project_id}/eap",
    response_model=EAPItemResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_eap_item(
    project_id: str,
    payload: EAPItemCreate,
    user: User = Depends(require_permission("field:write")),
    db: Session = Depends(get_db),
):
    get_project_or_404(db, project_id, user)

    if payload.parent_id:
        parent = (
            tenant_query(db, EAPItem, user)
            .filter(EAPItem.id == payload.parent_id, EAPItem.project_id == project_id)
            .first()
        )
        if not parent:
            raise HTTPException(
                status_code=422,
                detail="Item pai da EAP não encontrado neste empreendimento.",
            )

    item = EAPItem(
        organization_id=user.organization_id,
        project_id=project_id,
        **payload.model_dump(),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


# --- Tarefas ----------------------------------------------------------------

@router.get("/projects/{project_id}/tasks", response_model=List[TaskItemResponse])
def list_project_tasks(
    project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    get_project_or_404(db, project_id, user)
    return (
        tenant_query(db, TaskItem, user)
        .filter(TaskItem.project_id == project_id)
        .order_by(TaskItem.created_at.desc())
        .all()
    )


@router.post(
    "/projects/{project_id}/tasks",
    response_model=TaskItemResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_task_item(
    project_id: str,
    payload: TaskItemCreate,
    user: User = Depends(require_permission("field:write")),
    db: Session = Depends(get_db),
):
    get_project_or_404(db, project_id, user)

    if payload.client_token:
        # Idempotência para a fila offline de campo (§3.7) — ver `daily_log`.
        existente = (
            tenant_query(db, TaskItem, user)
            .filter(
                TaskItem.project_id == project_id,
                TaskItem.client_token == payload.client_token,
            )
            .first()
        )
        if existente:
            return existente

    if payload.eap_item_id:
        eap_item = (
            tenant_query(db, EAPItem, user)
            .filter(EAPItem.id == payload.eap_item_id, EAPItem.project_id == project_id)
            .first()
        )
        if not eap_item:
            raise HTTPException(
                status_code=422,
                detail="Item de EAP não encontrado neste empreendimento.",
            )

    task = TaskItem(
        organization_id=user.organization_id,
        project_id=project_id,
        created_by_id=user.id,
        **payload.model_dump(),
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.patch("/tasks/{task_id}", response_model=TaskItemResponse)
def update_task_item(
    task_id: str,
    payload: TaskItemUpdate,
    user: User = Depends(require_permission("field:write")),
    db: Session = Depends(get_db),
):
    task = get_scoped_or_404(db, TaskItem, task_id, user, "Tarefa")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(task, key, value)
    db.commit()
    db.refresh(task)
    return task
