"""Sondas de saúde (§12 — observabilidade).

Até aqui `/health` devolvia `{"status": "healthy"}` **sem verificar nada**.
Respondia saudável com o banco fora do ar, e um orquestrador que confiasse nele
manteria em rotação um processo incapaz de atender. É o mesmo defeito do diário
que nascia `"assinado"`: afirmação sobre um estado que ninguém apurou.

Duas sondas, porque as perguntas são diferentes:

- **`/health`** — *o processo está vivo?* Barata, sem tocar em dependência.
  É o que um orquestrador consulta para decidir se reinicia o contêiner. Uma
  sonda de vida que consulta o banco derruba a aplicação inteira quando o banco
  oscila, que é o oposto do que se quer;
- **`/health/ready`** — *dá para atender?* Verifica cada dependência e devolve
  **503** se alguma essencial estiver fora. É o que decide se o processo entra
  no balanceador.

E o princípio do I10 vale aqui inteiro: **componente que não pôde ser
verificado responde `nao_verificado`, nunca `ok`**. Antivírus desligado por
configuração não é antivírus funcionando.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app.core.config import settings
from app.core.database import SessionLocal

router = APIRouter()
logger = logging.getLogger("atlas.health")

#: Dependências sem as quais a API não atende. As demais entram no relatório,
#: mas não derrubam a prontidão: sem antivírus o upload é recusado (§6.6), e
#: recusar upload é degradação, não indisponibilidade.
ESSENTIAL = ("database",)


def _check_database() -> Dict[str, Any]:
    session = SessionLocal()
    try:
        session.execute(text("SELECT 1"))
        return {"status": "ok", "dialect": session.bind.dialect.name}
    except Exception as exc:  # noqa: BLE001 — a falha é o resultado
        return {"status": "falhou", "detail": f"{type(exc).__name__}: {exc}"}
    finally:
        session.close()


def _check_storage() -> Dict[str, Any]:
    try:
        from app.services.storage import get_storage

        return {"status": "ok", "backend": get_storage().describe()}
    except Exception as exc:  # noqa: BLE001
        return {"status": "falhou", "detail": f"{type(exc).__name__}: {exc}"}


def _check_queue() -> Dict[str, Any]:
    try:
        from app.workers.queue import get_queue

        descricao = get_queue().describe()
    except Exception as exc:  # noqa: BLE001
        return {"status": "falhou", "detail": f"{type(exc).__name__}: {exc}"}

    if settings.QUEUE_BACKEND == "inline":
        # Não é falha: é modo declarado. Mas quem lê precisa saber que não há
        # worker, e que o trabalho roda no próprio request (§6.7).
        return {"status": "inline", "backend": descricao}
    return {"status": "ok", "backend": descricao}


def _check_antivirus() -> Dict[str, Any]:
    if settings.ANTIVIRUS_BACKEND == "none":
        return {
            "status": "nao_verificado",
            "detail": "ANTIVIRUS_BACKEND=none — nenhuma varredura configurada.",
        }
    try:
        from app.services.antivirus import ClamAVScanner

        versao = ClamAVScanner()._version()
    except Exception as exc:  # noqa: BLE001
        return {"status": "falhou", "detail": f"{type(exc).__name__}: {exc}"}

    if not versao:
        # Daemon fora do ar. Com ANTIVIRUS_REQUIRED, todo upload será recusado
        # — degradação severa, e precisa aparecer.
        return {"status": "falhou", "detail": "clamd não respondeu ao VERSION."}
    return {"status": "ok", "engine": versao}


@router.get("/health")
def liveness():
    """O processo responde. Não consulta dependência nenhuma, de propósito."""
    return {
        "status": "vivo",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
    }


@router.get("/health/ready")
def readiness(response: Response):
    """Dá para atender? Verifica cada dependência e diz o que encontrou.

    Devolve **503** quando alguma dependência essencial falha, para que um
    balanceador tire o processo de rotação em vez de mandar tráfego para ele.
    """
    componentes = {
        "database": _check_database(),
        "storage": _check_storage(),
        "queue": _check_queue(),
        "antivirus": _check_antivirus(),
    }

    indisponiveis = [
        nome
        for nome in ESSENTIAL
        if componentes[nome]["status"] not in ("ok", "inline")
    ]

    if indisponiveis:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        logger.error(
            "Prontidão negada",
            extra={"componentes_indisponiveis": indisponiveis},
        )

    return {
        "status": "indisponivel" if indisponiveis else "pronto",
        "components": componentes,
    }
