from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.v1.router import api_router

# O esquema é criado por migrations versionadas (alembic upgrade head),
# não em tempo de import. Ver backend/alembic/ e o README.

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    description=(
        "Atlas — plataforma para aprovação, planejamento, execução e gestão de "
        "empreendimentos. Todos os endpoints de negócio exigem autenticação "
        "Bearer e operam restritos à organização do usuário."
    )
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[
        "X-Atlas-Publishable",
        "X-Atlas-Content-Hash",
        "X-Atlas-Analysis-Run",
        "X-Atlas-Pdf-Sha256",
        "X-Atlas-Document-Status",
        "X-Atlas-Antivirus-Status",
    ],
)

app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/")
def root():
    return {
        "name": settings.PROJECT_NAME,
        "docs": "/docs",
        "version": settings.VERSION,
        "message": "Atlas System Operational"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
