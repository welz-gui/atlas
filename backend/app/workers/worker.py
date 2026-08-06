"""Processo worker (§6.7).

    python -m app.workers.worker
    python -m app.workers.worker --queue laudos --recover

Consome identificadores do broker e executa o trabalho correspondente. Duas
responsabilidades que o consumidor de fila comum não tem:

- **recuperar órfãos.** Como o estado vive no banco, um trabalho que ficou
  `enfileirado` sem ninguém para pegá-lo — Redis reiniciado, worker morto
  entre publicar e consumir — é encontrado por varredura, não por
  arqueologia no broker. `--recover` faz essa varredura na partida.
- **reenfileirar o que falhou.** `run_job` devolve o trabalho para
  `enfileirado` enquanto restarem tentativas; é aqui que ele volta à fila.

Sem broker configurado o worker não sobe: não faz sentido ter processo
dedicado a uma fila que não existe. A mensagem diz isso em vez de o processo
ficar girando em falso.
"""

from __future__ import annotations

import argparse
import logging
import signal
import sys
from datetime import datetime, timedelta
from typing import Optional

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.domain import JobRecord, JobStatus
from app.workers.queue import get_queue, run_job, worker_identity

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s — %(message)s",
)
logger = logging.getLogger("atlas.worker")

_stop = False


def _handle_signal(signum, _frame):
    """Encerra depois de terminar o trabalho em curso, nunca no meio dele."""
    global _stop
    _stop = True
    logger.info("Sinal %s recebido; encerrando após o trabalho atual.", signum)


def requeue_orphans(queue_name: str, older_than_minutes: int = 5) -> int:
    """Republica trabalhos que ficaram parados na fila.

    Só alcança registros parados há algum tempo: republicar um trabalho
    publicado há dois segundos duplicaria execução à toa.
    """
    cutoff = datetime.utcnow() - timedelta(minutes=older_than_minutes)
    broker = get_queue()
    db = SessionLocal()
    try:
        orphans = (
            db.query(JobRecord)
            .filter(
                JobRecord.status == JobStatus.ENFILEIRADO,
                JobRecord.queue == queue_name,
                JobRecord.executed_inline.is_(False),
                JobRecord.queued_at <= cutoff,
            )
            .all()
        )
        for job in orphans:
            broker.publish(job.id, queue_name)
        if orphans:
            logger.info("%d trabalho(s) órfão(s) republicado(s).", len(orphans))
        return len(orphans)
    finally:
        db.close()


def process_once(queue_name: str, timeout: int = 5) -> Optional[str]:
    """Pega um trabalho e o executa. Devolve o id, ou None se a fila estava vazia."""
    broker = get_queue()
    job_id = broker.consume(queue_name, timeout=timeout)
    if not job_id:
        return None

    db = SessionLocal()
    try:
        record = run_job(db, job_id)
        logger.info(
            "Trabalho %s (%s) → %s%s",
            record.id,
            record.job_type,
            record.status,
            f" em {record.duration_seconds}s" if record.duration_seconds else "",
        )
        # Falhou mas ainda tem tentativa: volta para a fila.
        if record.status == JobStatus.ENFILEIRADO:
            broker.publish(record.id, queue_name)
    finally:
        db.close()

    acknowledge = getattr(broker, "acknowledge", None)
    if acknowledge:
        acknowledge(job_id, queue_name)
    return job_id


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Worker de trabalhos do Atlas (§6.7).")
    parser.add_argument("--queue", default="default", help="Fila a consumir.")
    parser.add_argument(
        "--timeout", type=int, default=5, help="Segundos de espera por trabalho."
    )
    parser.add_argument(
        "--recover",
        action="store_true",
        help="Republica trabalhos parados na fila antes de começar.",
    )
    parser.add_argument(
        "--once", action="store_true", help="Processa um trabalho e encerra."
    )
    args = parser.parse_args(argv)

    broker = get_queue()
    if not broker.is_async:
        logger.error(
            "QUEUE_BACKEND=%s não tem broker: os trabalhos executam no próprio "
            "processo da API e não há fila para consumir. Configure "
            "QUEUE_BACKEND=redis e REDIS_URL para rodar workers.",
            settings.QUEUE_BACKEND,
        )
        return 2

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    logger.info(
        "Worker %s consumindo '%s' via %s",
        worker_identity(),
        args.queue,
        broker.describe(),
    )

    if args.recover:
        requeue_orphans(args.queue)

    while not _stop:
        process_once(args.queue, timeout=args.timeout)
        if args.once:
            break

    logger.info("Worker encerrado.")
    return 0


if __name__ == "__main__":  # pragma: no cover - ponto de entrada
    sys.exit(main())
