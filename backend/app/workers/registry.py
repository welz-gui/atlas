from typing import Any, Callable, Dict
from sqlalchemy.orm import Session
from app.models.domain import JobRecord

HANDLERS: Dict[str, Callable[[Session, JobRecord], Dict[str, Any]]] = {}

def register(job_type: str):
    """Decorador que liga um tipo de trabalho ao seu executor."""

    def wrapper(func):
        HANDLERS[job_type] = func
        return func

    return wrapper
