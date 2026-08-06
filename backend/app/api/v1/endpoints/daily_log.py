from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.models.domain import Project, DailyLog
from app.schemas.domain import DailyLogCreate, DailyLogResponse

router = APIRouter()

@router.get("/projects/{project_id}/daily-logs", response_model=List[DailyLogResponse])
def list_project_daily_logs(project_id: str, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return db.query(DailyLog).filter(DailyLog.project_id == project_id).order_by(DailyLog.date.desc()).all()

@router.post("/projects/{project_id}/daily-logs", response_model=DailyLogResponse, status_code=status.HTTP_201_CREATED)
def create_daily_log(project_id: str, log_data: DailyLogCreate, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    db_log = DailyLog(
        project_id=project_id,
        date=log_data.date,
        weather_condition=log_data.weather_condition,
        manpower_own=log_data.manpower_own,
        manpower_subcontracted=log_data.manpower_subcontracted,
        activities_done=log_data.activities_done,
        occurrences=log_data.occurrences,
        status=log_data.status
    )
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    return db_log
