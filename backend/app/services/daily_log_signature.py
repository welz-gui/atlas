"""Assinatura do diário de obra (§8.12 — item D4).

Até a Fase D, `status` nascia como `"assinado"` por `default`. Era literal
falso: todo diário afirmava um ato humano que nunca aconteceu — inclusive os
que chegavam pela fila offline, quando ninguém estava diante de tela alguma.

O que uma assinatura precisa dizer para não ser decorativa:

- **quem** assinou, com o nome que a pessoa tinha naquele dia;
- **quando**;
- **o quê** — e é aqui que o hash entra. Sem ele, "assinado" não distingue o
  texto que a pessoa leu do texto que alguém editou depois.

O hash é sobre o conteúdo canônico, não sobre a linha inteira: campos de
controle mudam por motivos que não alteram o que foi relatado. Recalcular e
comparar responde se o diário ainda é o que foi assinado — é o mesmo mecanismo
do `content_hash` de `AnalysisRun` (§3.5).
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Optional

from app.models.domain import DailyLog, DailyLogState, User

#: Campos que compõem o que foi relatado. Alterar qualquer um deles depois da
#: assinatura quebra o hash — que é o ponto.
SIGNED_FIELDS = (
    "project_id",
    "date",
    "weather_condition",
    "manpower_own",
    "manpower_subcontracted",
    "activities_done",
    "occurrences",
)


def content_hash(log: DailyLog) -> str:
    """SHA-256 do conteúdo canônico do diário.

    `sort_keys` e separadores fixos existem para que o mesmo conteúdo produza
    sempre o mesmo hash, independentemente da ordem em que os campos foram
    escritos ou da versão do Python.
    """
    canonical = json.dumps(
        {campo: getattr(log, campo) for campo in SIGNED_FIELDS},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def sign(db, log: DailyLog, user: User, when: Optional[datetime] = None) -> DailyLog:
    """Registra a assinatura: quem, quando e sobre qual conteúdo."""
    log.content_hash = content_hash(log)
    log.signed_by_id = user.id
    log.signed_by_name = user.name
    log.signed_at = when or datetime.utcnow()
    log.status = DailyLogState.ASSINADO
    db.commit()
    db.refresh(log)
    return log


def signature_is_valid(log: DailyLog) -> Optional[bool]:
    """`True`, `False` ou `None` — e os três significam coisas diferentes.

    `None` é diário não assinado: não há assinatura para conferir, e dizer
    `False` afirmaria adulteração onde há apenas ausência. É o invariante I1
    aplicado à assinatura.
    """
    if log.status != DailyLogState.ASSINADO or not log.content_hash:
        return None
    return log.content_hash == content_hash(log)
