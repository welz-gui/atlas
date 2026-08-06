from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.models.domain import Project, EAPItem, TaskItem
from app.schemas.domain import (
    EAPItemCreate, EAPItemResponse,
    TaskItemCreate, TaskItemUpdate, TaskItemResponse
)

router = APIRouter()

# --- EAP (Estrutura Analítica do Projeto) ---
@router.get("/projects/{project_id}/eap", response_model=List[EAPItemResponse])
def list_project_eap(project_id: str, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return db.query(EAPItem).filter(EAPItem.project_id == project_id).order_by(EAPItem.code).all()

@router.post("/projects/{project_id}/eap", response_model=EAPItemResponse, status_code=status.HTTP_201_CREATED)
def create_eap_item(project_id: str, eap: EAPItemCreate, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    db_eap = EAPItem(
        project_id=project_id,
        code=eap.code,
        name=eap.name,
        item_type=eap.item_type,
        progress_percent=eap.progress_percent,
        parent_id=eap.parent_id
    )
    db.add(db_eap)
    db.commit()
    db.refresh(db_eap)
    return db_eap

# --- Kanban Tasks ---
@router.get("/projects/{project_id}/tasks", response_model=List[TaskItemResponse])
def list_project_tasks(project_id: str, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return db.query(TaskItem).filter(TaskItem.project_id == project_id).all()

@router.post("/projects/{project_id}/tasks", response_model=TaskItemResponse, status_code=status.HTTP_201_CREATED)
def create_task_item(project_id: str, task: TaskItemCreate, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    db_task = TaskItem(
        project_id=project_id,
        eap_item_id=task.eap_item_id,
        title=task.title,
        description=task.description,
        status=task.status,
        priority=task.priority,
        assignee=task.assignee,
        due_date=task.due_date
    )
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task

@router.patch("/tasks/{task_id}", response_model=TaskItemResponse)
def update_task_item(task_id: str, task_update: TaskItemUpdate, db: Session = Depends(get_db)):
    task = db.query(TaskItem).filter(TaskItem.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
        
    update_data = task_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(task, key, value)
        
    db.commit()
    db.refresh(task)
    return task
