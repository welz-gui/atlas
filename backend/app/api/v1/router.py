from fastapi import APIRouter

from app.api.v1.endpoints import (
    ai,
    auth,
    catalog,
    daily_log,
    documents,
    health,
    jobs,
    metrics,
    plan,
    portal,
    projects,
    protocol,
    regulatory,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(auth.router, tags=["Autenticação e usuários"])
api_router.include_router(projects.router, tags=["Empreendimentos e versões"])
api_router.include_router(regulatory.router, tags=["Copiloto de aprovação"])
api_router.include_router(catalog.router, tags=["Catálogo regulatório e validação"])
api_router.include_router(protocol.router, tags=["Tramitação municipal"])
api_router.include_router(documents.router, tags=["Gestão documental"])
api_router.include_router(jobs.router, tags=["Trabalhos assíncronos"])
api_router.include_router(plan.router, tags=["Planejamento — EAP e tarefas"])
api_router.include_router(daily_log.router, tags=["Diário de obra"])
api_router.include_router(ai.router, tags=["Assistente normativo"])
api_router.include_router(portal.router, tags=["Portal do cliente"])
api_router.include_router(metrics.router, tags=["Métricas (§11)"])
