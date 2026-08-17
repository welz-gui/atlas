from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import logging
import time
import uuid

from app.core.config import settings
from app.core.logging import configure_logging, reset_request_id, set_request_id
from app.core.tenant import current_organization_id
from app.core.tenant import reset_current_organization, set_current_organization

configure_logging(settings.LOG_LEVEL)
logger = logging.getLogger("atlas.api")
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

@app.middleware("http")
async def observability(request, call_next):
    """Correlaciona e registra cada requisição (§12 — observabilidade).

    O identificador vem do cliente quando ele manda `X-Request-Id` — assim uma
    chamada que atravessa serviços mantém o mesmo fio — e é gerado aqui quando
    não vem. Volta sempre no cabeçalho, para que o relato de quem viu o erro
    carregue a chave que acha a linha do servidor.

    O que se registra é a **forma** da requisição, nunca o conteúdo: método,
    rota, situação, duração e organização. Corpo e query string ficam de fora
    porque carregam dado pessoal (`docs/LGPD.md`).
    """
    request_id = request.headers.get("X-Request-Id") or uuid.uuid4().hex
    token = set_request_id(request_id)
    inicio = time.perf_counter()

    try:
        response = await call_next(request)
    except Exception:
        # Exceção não tratada precisa deixar rastro antes de virar 500 genérico.
        logger.exception(
            "Requisição falhou",
            extra={
                "method": request.method,
                "path": request.url.path,
                "duration_ms": round((time.perf_counter() - inicio) * 1000, 1),
                "organization_id": current_organization_id(),
            },
        )
        reset_request_id(token)
        raise

    duracao = round((time.perf_counter() - inicio) * 1000, 1)
    response.headers["X-Request-Id"] = request_id

    # 5xx é problema nosso; 4xx é do pedido. O nível reflete isso, para que
    # alerta futuro possa filtrar por severidade sem ler mensagem.
    nivel = logging.ERROR if response.status_code >= 500 else logging.INFO
    logger.log(
        nivel,
        "Requisição atendida",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": duracao,
            "organization_id": current_organization_id(),
        },
    )

    reset_request_id(token)
    return response


@app.middleware("http")
async def tenant_scope(request, call_next):
    """Garante que a organização não sobreviva à requisição (§3.1, D1).

    `get_current_user` põe a organização em vigor e não a desfaz, porque ela
    precisa valer até o fim do tratamento. Quem desfaz é este middleware — em
    qualquer saída, inclusive erro.

    Sem isto, o contexto de execução reaproveitado pela requisição seguinte
    herdaria a organização anterior, que é precisamente o vazamento que a RLS
    existe para impedir.
    """
    token = set_current_organization(None)
    try:
        return await call_next(request)
    finally:
        reset_current_organization(token)


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
