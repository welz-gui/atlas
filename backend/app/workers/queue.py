"""Filas e trabalhos assíncronos (§6.7).

O problema que isto resolve: extração de PDF, execução do catálogo e geração de
laudo rodavam dentro do request. Um arquivo grande fazia o navegador esperar; um
timeout de proxy derrubava a operação no meio, sem deixar rastro de que ela
havia começado.

**O banco é a fonte da verdade; o Redis é só o canal de aviso.** Cada trabalho
nasce como uma linha em `job_records`, com quem pediu, quando, sobre o quê e o
que aconteceu. O que trafega pelo broker é apenas o identificador. Essa escolha
tem três consequências que valem mais do que a comodidade de um framework de
filas:

- um Redis reiniciado não apaga trabalho nenhum: as linhas continuam
  `enfileirado`, visíveis e recuperáveis;
- a trilha de auditoria (§3.5) não depende de um sistema externo;
- não é preciso Celery nem Dramatiq para ter fila confiável — o broker carrega
  um UUID, e isso é tudo o que se pede dele.

**Sem broker, o trabalho roda no próprio processo** e a linha fica marcada com
`executed_inline=True`. Uma instalação de desenvolvimento continua funcionando;
o que ela não faz é fingir ter uma fila que não tem.
"""

from __future__ import annotations

import logging
import os
import socket
import traceback
from abc import ABC, abstractmethod
from datetime import datetime
from functools import lru_cache
from typing import Any, Callable, Dict, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.domain import JobRecord, JobStatus, User

logger = logging.getLogger("atlas.workers")

#: Handlers registrados por tipo de trabalho. Preenchido por
#: `app.workers.tasks`, que é importado ao final deste módulo para evitar
#: dependência circular.
HANDLERS: Dict[str, Callable[[Session, JobRecord], Dict[str, Any]]] = {}


def register(job_type: str):
    """Decorador que liga um tipo de trabalho ao seu executor."""

    def wrapper(func):
        HANDLERS[job_type] = func
        return func

    return wrapper


def worker_identity() -> str:
    return f"{socket.gethostname()}:{os.getpid()}"


# =============================================================================
# Backends de fila
# =============================================================================

class QueueBackend(ABC):
    name: str

    @abstractmethod
    def publish(self, job_id: str, queue: str = "default") -> None:
        """Avisa que há trabalho a fazer."""

    @abstractmethod
    def consume(self, queue: str = "default", timeout: int = 5) -> Optional[str]:
        """Bloqueia até haver trabalho, ou devolve None ao esgotar o tempo."""

    @property
    def is_async(self) -> bool:
        """Falso quando não há worker separado — o trabalho roda no request."""
        return True

    def describe(self) -> str:
        return self.name


class InlineQueue(QueueBackend):
    """Ausência de fila, dita com todas as letras.

    Não guarda nada e não entrega nada: quem enfileira executa. É o padrão de
    desenvolvimento, e o registro do trabalho deixa isso explícito.
    """

    name = "inline"

    def publish(self, job_id: str, queue: str = "default") -> None:
        return None

    def consume(self, queue: str = "default", timeout: int = 5) -> Optional[str]:
        return None

    @property
    def is_async(self) -> bool:
        return False

    def describe(self) -> str:
        return "sem broker — trabalhos executam no próprio processo"


class RedisQueue(QueueBackend):
    """Fila confiável sobre listas do Redis.

    Usa `BLMOVE` da fila para uma lista de processamento: se o worker morrer
    entre pegar e concluir, o identificador continua na lista de processamento
    em vez de sumir. Como o estado real vive no banco, a recuperação é uma
    varredura por `enfileirado` antigo — não uma reconstrução do broker.
    """

    name = "redis"

    def __init__(self, url: Optional[str] = None, client=None):
        self.url = url or settings.REDIS_URL
        if not self.url:
            raise RuntimeError("QUEUE_BACKEND=redis exige REDIS_URL configurado.")
        self._client = client

    @property
    def client(self):
        if self._client is None:
            try:
                import redis  # noqa: PLC0415 — dependência opcional
            except ImportError as exc:  # pragma: no cover - depende do ambiente
                raise RuntimeError(
                    "QUEUE_BACKEND=redis exige o pacote redis instalado."
                ) from exc
            self._client = redis.Redis.from_url(self.url, decode_responses=True)
        return self._client

    def _key(self, queue: str) -> str:
        return f"atlas:queue:{queue}"

    def _processing_key(self, queue: str) -> str:
        return f"atlas:queue:{queue}:processing"

    def publish(self, job_id: str, queue: str = "default") -> None:
        self.client.lpush(self._key(queue), job_id)

    def consume(self, queue: str = "default", timeout: int = 5) -> Optional[str]:
        return self.client.blmove(
            self._key(queue), self._processing_key(queue), timeout, "RIGHT", "LEFT"
        )

    def acknowledge(self, job_id: str, queue: str = "default") -> None:
        self.client.lrem(self._processing_key(queue), 1, job_id)

    def describe(self) -> str:
        return f"redis ({self.url})"


_BACKENDS = {"inline": InlineQueue, "redis": RedisQueue}


@lru_cache(maxsize=1)
def get_queue() -> QueueBackend:
    choice = (settings.QUEUE_BACKEND or "inline").strip().lower()
    factory = _BACKENDS.get(choice)
    if factory is None:
        raise RuntimeError(
            f"QUEUE_BACKEND='{choice}' desconhecido. "
            f"Valores aceitos: {', '.join(sorted(_BACKENDS))}."
        )
    return factory()


def reset_queue_cache() -> None:
    get_queue.cache_clear()


# =============================================================================
# Enfileirar e executar
# =============================================================================

def enqueue(
    db: Session,
    job_type: str,
    payload: Optional[Dict[str, Any]] = None,
    user: Optional[User] = None,
    organization_id: Optional[str] = None,
    project_id: Optional[str] = None,
    queue: str = "default",
    backend: Optional[QueueBackend] = None,
) -> JobRecord:
    """Cria o registro do trabalho e o entrega — ao broker ou a si mesmo.

    O commit do registro acontece **antes** da publicação: um trabalho anunciado
    que ainda não existisse no banco seria um identificador órfão para o worker.
    """
    if job_type not in HANDLERS:
        raise ValueError(
            f"Tipo de trabalho '{job_type}' não tem executor registrado. "
            f"Conhecidos: {', '.join(sorted(HANDLERS)) or 'nenhum'}."
        )

    org_id = organization_id or (user.organization_id if user else None)
    if not org_id:
        raise ValueError("Todo trabalho pertence a uma organização (§3.1).")

    record = JobRecord(
        organization_id=org_id,
        project_id=project_id,
        job_type=job_type,
        payload=payload or {},
        status=JobStatus.ENFILEIRADO,
        queue=queue,
        requested_by_id=user.id if user else None,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    broker = backend or get_queue()
    if broker.is_async:
        broker.publish(record.id, queue)
    else:
        # Sem broker, quem pede executa. O registro guarda essa circunstância.
        record.executed_inline = True
        db.commit()
        # As retentativas também acontecem aqui: não há worker que fosse
        # buscar de volta um trabalho deixado em `enfileirado`, e devolver ao
        # chamador um trabalho que ninguém retomaria seria mentir sobre o
        # estado dele. Execução inline termina sempre em estado terminal.
        while not run_job(db, record.id).is_terminal:
            pass
        db.refresh(record)

    return record


def run_job(db: Session, job_id: str) -> JobRecord:
    """Executa um trabalho e registra o desfecho, qualquer que seja ele.

    Nenhum caminho sai daqui deixando a linha em `executando`: sucesso, falha
    ou exceção inesperada, o estado final sempre é gravado. Um trabalho que
    fica preso em `executando` significa processo morto — e é assim que se lê.
    """
    record = db.query(JobRecord).filter(JobRecord.id == job_id).first()
    if record is None:
        raise LookupError(f"Trabalho '{job_id}' não encontrado.")

    if record.is_terminal:
        return record

    handler = HANDLERS.get(record.job_type)
    if handler is None:
        record.status = JobStatus.FALHOU
        record.error = f"Nenhum executor registrado para '{record.job_type}'."
        record.finished_at = datetime.utcnow()
        db.commit()
        return record

    record.status = JobStatus.EXECUTANDO
    record.started_at = datetime.utcnow()
    record.attempts += 1
    record.worker_id = worker_identity()
    db.commit()

    try:
        result = handler(db, record)
    except Exception as exc:  # noqa: BLE001 — a falha precisa virar registro
        db.rollback()
        record = db.query(JobRecord).filter(JobRecord.id == job_id).first()
        record.error = f"{type(exc).__name__}: {exc}"
        record.finished_at = datetime.utcnow()
        # Esgotadas as tentativas, o trabalho falha de vez. Antes disso volta
        # para a fila — mas quem republica é o worker, que sabe se há broker.
        record.status = (
            JobStatus.FALHOU
            if record.attempts >= record.max_attempts
            else JobStatus.ENFILEIRADO
        )
        db.commit()
        logger.warning(
            "Trabalho %s (%s) falhou na tentativa %d/%d: %s",
            record.id,
            record.job_type,
            record.attempts,
            record.max_attempts,
            exc,
        )
        logger.debug(traceback.format_exc())
        return record

    record.status = JobStatus.CONCLUIDO
    record.result = result if isinstance(result, dict) else {"value": result}
    record.finished_at = datetime.utcnow()
    db.commit()
    db.refresh(record)
    return record


# Importado por último: `tasks` depende de `register`, definido acima.
from app.workers import tasks  # noqa: E402,F401
