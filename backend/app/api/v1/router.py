from fastapi import APIRouter
from app.api.v1.endpoints import health, projects, regulatory, documents, plan, ai, daily_log

api_router = APIRouter()
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(projects.router, tags=["Organizations & Projects"])
api_router.include_router(regulatory.router, tags=["Regulatory Copilot"])
api_router.include_router(documents.router, tags=["Document Management & SHA-256"])
api_router.include_router(plan.router, tags=["Atlas Plan - EAP & Kanban Tasks"])
api_router.include_router(ai.router, tags=["Atlas AI - Urbanistic Legislation Assistant"])
api_router.include_router(daily_log.router, tags=["Daily Log - Diário de Obra Digital"])
