"""Política de retenção de documentos (§6.6).

O que esta política apaga é o **binário**, nunca o registro. Um documento
expurgado continua na tabela, com título, versão, hash, autor, data e a marca
de quando e por que o arquivo saiu do armazenamento. Isso preserva a exigência
de auditabilidade (§3.5) — se alguém perguntar, daqui a três anos, qual prancha
estava vigente no dia do protocolo, a resposta continua existindo, ainda que o
PDF já não esteja.

O relógio só começa a correr quando o documento sai de circulação: enquanto
estiver `vigente`, nada é descartado, por mais antigo que seja. A janela vem de
`OBSOLETE_RETENTION_DAYS`; zero — o padrão — desliga o expurgo por completo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.domain import Document, DocumentState
from app.services.storage import ObjectNotFound, StorageBackend, get_storage


def retention_deadline(
    obsolete_at: datetime, retention_days: Optional[int] = None
) -> Optional[datetime]:
    """Data a partir da qual o binário pode ser descartado.

    `None` significa guardar indefinidamente — que é o comportamento padrão.
    """
    days = settings.OBSOLETE_RETENTION_DAYS if retention_days is None else retention_days
    if days <= 0:
        return None
    return obsolete_at + timedelta(days=days)


def mark_obsolete(document: Document, when: Optional[datetime] = None) -> Document:
    """Tira o documento de circulação e agenda a retenção do binário.

    Ponto único de saída de circulação: quem marca um documento como obsoleto
    passa por aqui, para que a data de retenção nunca fique por preencher.
    """
    moment = when or datetime.utcnow()
    document.status = DocumentState.OBSOLETO
    document.superseded_at = moment
    document.retention_until = retention_deadline(moment)
    return document


@dataclass
class PurgeReport:
    """O que o expurgo fez — ou faria, em simulação."""

    dry_run: bool = False
    examined: int = 0
    purged: int = 0
    already_missing: int = 0
    failed: int = 0
    document_ids: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    @property
    def retention_enabled(self) -> bool:
        return settings.OBSOLETE_RETENTION_DAYS > 0


def eligible_documents(
    db: Session,
    organization_id: Optional[str] = None,
    now: Optional[datetime] = None,
) -> List[Document]:
    """Documentos obsoletos cuja janela de retenção venceu.

    Um documento sem `retention_until` nunca é elegível: ausência de prazo
    significa guardar, não significa 'expurgar agora'.
    """
    moment = now or datetime.utcnow()
    query = (
        db.query(Document)
        .filter(
            Document.status == DocumentState.OBSOLETO,
            Document.purged_at.is_(None),
            Document.retention_until.isnot(None),
            Document.retention_until <= moment,
        )
    )
    if organization_id:
        query = query.filter(Document.organization_id == organization_id)
    return query.order_by(Document.retention_until).all()


def purge_expired_documents(
    db: Session,
    organization_id: Optional[str] = None,
    now: Optional[datetime] = None,
    dry_run: bool = False,
    storage: Optional[StorageBackend] = None,
) -> PurgeReport:
    """Descarta o binário dos documentos vencidos, preservando os metadados."""
    backend = storage or get_storage()
    moment = now or datetime.utcnow()
    report = PurgeReport(dry_run=dry_run)

    for document in eligible_documents(db, organization_id, moment):
        report.examined += 1
        report.document_ids.append(document.id)
        if dry_run:
            continue

        try:
            removed = backend.delete(document.file_path)
        except ObjectNotFound:
            removed = False
        except Exception as exc:  # falha de rede/permissão no backend remoto
            report.failed += 1
            report.errors.append(f"{document.id}: {exc}")
            continue

        if not removed:
            # O arquivo já não estava lá. O registro precisa refletir isso do
            # mesmo jeito: o que importa para quem consulta é que o binário não
            # existe mais, e não quem o removeu primeiro.
            report.already_missing += 1

        document.purged_at = moment
        document.purge_reason = (
            f"Retenção de {settings.OBSOLETE_RETENTION_DAYS} dia(s) após "
            f"obsolescência (§6.6)."
        )
        report.purged += 1

    if not dry_run and report.purged:
        db.commit()

    return report
