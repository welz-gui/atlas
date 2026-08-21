"""Métricas do §11, calculadas sobre o dado que já existe (item D5).

Uma regra governa este módulo inteiro:

    **Ausência de base amostral devolve `None`, nunca zero.**

Zero é uma afirmação — "nenhuma exigência escapou". `None` é a ausência dela —
"não houve exigência para escapar". Confundir os dois faz um Portão 0 → 1 ser
atravessado por uma organização que nunca protocolou nada. É o invariante I1
aplicado a métrica: ausência de dado não vira veredicto.

Nada aqui estima. Onde o cálculo exigiria uma suposição — preço de token, por
exemplo — o campo não existe, e o motivo está escrito no schema.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.domain import (
    AIInteraction,
    AnalysisRun,
    Project,
    ProtocolEvent,
    ProtocolProcess,
    ProtocolRequirement,
    ProtocolStatus,
    RegulatoryRule,
    RuleValidationEvent,
)
from app.regulatory.catalog import CheckOutcome, RuleState
from app.regulatory.jurisdiction import applicable_jurisdictions

#: Veredictos que contam como "o motor apontou isto".
FLAGGED = (CheckOutcome.NAO_CONFORME, CheckOutcome.ATENCAO)


def _percent(part: int, whole: int) -> Optional[float]:
    """Percentual, ou `None` quando não há denominador."""
    if whole <= 0:
        return None
    return round(part / whole * 100, 1)


def _mean(values: list[float]) -> Optional[float]:
    if not values:
        return None
    return round(sum(values) / len(values), 1)


def _parse_date(raw: Optional[str]) -> Optional[date]:
    """As datas de tramitação são texto ISO vindas do órgão (§8.5).

    Data ilegível é ausência de data, não erro: o processo continua válido, a
    métrica é que não pode ser calculada com ele.
    """
    if not raw:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


# --- Aprovação (§11) ---------------------------------------------------------



def _get_notification_events(db: Session, organization_id: str, process_ids: list[str]) -> int:
    # -- Ciclos de notificação -------------------------------------------
    # Cada volta do órgão é uma transição para `notificado`. Um processo que
    # foi notificado duas vezes custou dois ciclos ao cliente.
    return (
        db.query(ProtocolEvent)
        .filter(
            ProtocolEvent.organization_id == organization_id,
            ProtocolEvent.to_status == ProtocolStatus.NOTIFICADO,
        )
        .count()
        if process_ids
        else 0
    )


def _calculate_durations(processes: list[ProtocolProcess]) -> tuple[list[float], int]:
    # -- Dias até alvará --------------------------------------------------
    # Só processos decididos e aprovados entram. Processo em andamento não
    # tem duração; tem duração parcial, que é outra coisa.
    durations: list[float] = []
    approved = 0
    for process in processes:
        if process.status != ProtocolStatus.APROVADO:
            continue
        approved += 1
        submitted = _parse_date(process.submitted_at)
        decided = _parse_date(process.decided_at)
        if submitted and decided and decided >= submitted:
            durations.append((decided - submitted).days)
    return durations, approved


def _calculate_recall(requirements: list[ProtocolRequirement]) -> tuple[list[ProtocolRequirement], int, int]:
    # -- Recall de bloqueios e falsos negativos críticos -------------------
    # Só exigência vinculada a regra entra: exigência documental que nenhuma
    # regra poderia prever não é falha do motor.
    linked = [r for r in requirements if r.linked_rule_key]
    predicted = sum(1 for r in linked if r.was_predicted)
    false_negatives = sum(1 for r in linked if r.was_predicted is False)
    return linked, predicted, false_negatives


def _calculate_precision(db: Session, organization_id: str, processes: list[ProtocolProcess], requirements: list[ProtocolRequirement]) -> tuple[int, set[tuple[str, str]]]:
    # -- Precisão ---------------------------------------------------------
    # Do que o motor apontou, quanto o órgão confirmou. O denominador é o
    # conjunto de pares (projeto, regra) apontados na análise mais recente de
    # cada projeto que chegou a protocolar.
    protocolled_project_ids = {p.project_id for p in processes}
    required_pairs = {
        (process.project_id, r.linked_rule_key)
        for process in processes
        for r in requirements
        if r.process_id == process.id and r.linked_rule_key
    }

    flagged_pairs: set[tuple[str, str]] = set()
    for project_id in protocolled_project_ids:
        latest = (
            db.query(AnalysisRun)
            .filter(
                AnalysisRun.organization_id == organization_id,
                AnalysisRun.project_id == project_id,
            )
            .order_by(AnalysisRun.created_at.desc())
            .first()
        )
        if not latest:
            continue
        for record in latest.validations:
            if record.status in FLAGGED:
                flagged_pairs.add((project_id, record.rule_id))

    confirmed = len(flagged_pairs & required_pairs)
    return confirmed, flagged_pairs


def _calculate_unverifiable(db: Session, organization_id: str, project_ids: list[str]) -> tuple[int, int]:
    # -- Não verificáveis --------------------------------------------------
    # Sobre todas as análises mais recentes, não só as protocoladas: mede
    # quanto do projeto o sistema não consegue avaliar por falta de dado.
    total_checks = 0
    unverifiable = 0
    for project_id in project_ids:
        latest = (
            db.query(AnalysisRun)
            .filter(
                AnalysisRun.organization_id == organization_id,
                AnalysisRun.project_id == project_id,
            )
            .order_by(AnalysisRun.created_at.desc())
            .first()
        )
        if not latest:
            continue
        total_checks += latest.total_checks
        unverifiable += latest.nao_verificavel_count
    return total_checks, unverifiable


def _calculate_catalog_coverage(db: Session, projects: list[Project]) -> tuple[list[RegulatoryRule], int, set[str]]:
    # -- Cobertura do catálogo --------------------------------------------
    # Regra publicável sobre total, nas jurisdições em que a organização tem
    # projeto. É a medida do progresso do D3, e é o que decide se um laudo
    # pode ser entregue.
    jurisdictions = applicable_jurisdictions(
        {p.city_ibge for p in projects if p.city_ibge}
    )
    rules = (
        db.query(RegulatoryRule)
        .filter(RegulatoryRule.jurisdiction.in_(jurisdictions))
        .all()
        if jurisdictions
        else []
    )
    publishable = sum(
        1
        for r in rules
        if r.state == RuleState.VIGENTE and r.validated_by_id is not None
    )
    return rules, publishable, jurisdictions


def approval_metrics(db: Session, organization_id: str) -> dict[str, Any]:
    projects = db.query(Project).filter(Project.organization_id == organization_id).all()
    project_ids = [p.id for p in projects]

    processes = (
        db.query(ProtocolProcess)
        .filter(ProtocolProcess.organization_id == organization_id)
        .all()
    )
    process_ids = [p.id for p in processes]

    requirements = (
        db.query(ProtocolRequirement)
        .filter(ProtocolRequirement.organization_id == organization_id)
        .all()
        if process_ids
        else []
    )

    notification_events = _get_notification_events(db, organization_id, process_ids)
    durations, approved = _calculate_durations(processes)
    linked, predicted, false_negatives = _calculate_recall(requirements)
    confirmed, flagged_pairs = _calculate_precision(db, organization_id, processes, requirements)
    total_checks, unverifiable = _calculate_unverifiable(db, organization_id, project_ids)
    rules, publishable, jurisdictions = _calculate_catalog_coverage(db, projects)

    return {
        "projects": len(projects),
        "protocols": len(processes),
        "permits_granted": approved,
        "notification_cycles_total": notification_events if process_ids else None,
        "notification_cycles_per_protocol": (
            round(notification_events / len(processes), 2) if processes else None
        ),
        "days_to_permit_avg": _mean(durations),
        "requirements_total": len(requirements) if process_ids else None,
        "requirements_linked_to_rules": len(linked) if process_ids else None,
        "blocking_recall_percent": _percent(predicted, len(linked)),
        "critical_false_negatives": false_negatives if linked else None,
        "precision_percent": _percent(confirmed, len(flagged_pairs)),
        "unverifiable_percent": _percent(unverifiable, total_checks),
        "catalog_rules": len(rules) if jurisdictions else None,
        "catalog_publishable_rules": publishable if jurisdictions else None,
        "catalog_coverage_percent": _percent(publishable, len(rules)),
    }


# --- IA (§11) ----------------------------------------------------------------


def ai_metrics(db: Session, organization_id: str) -> dict[str, Any]:
    interactions = (
        db.query(AIInteraction)
        .filter(AIInteraction.organization_id == organization_id)
        .all()
    )

    grounded = sum(1 for i in interactions if i.grounded)
    cached = sum(1 for i in interactions if i.served_from_cache)
    failed = sum(1 for i in interactions if i.error)

    # Tokens são somados só onde o provedor os informou. Chamada servida do
    # cache não gasta token, e chamada sem provedor não tem token nenhum.
    with_tokens = [
        i for i in interactions if i.input_tokens is not None or i.output_tokens is not None
    ]
    input_tokens = sum(i.input_tokens or 0 for i in with_tokens)
    output_tokens = sum(i.output_tokens or 0 for i in with_tokens)

    analyses = (
        db.query(AnalysisRun)
        .filter(AnalysisRun.organization_id == organization_id)
        .count()
    )
    projects = (
        db.query(Project).filter(Project.organization_id == organization_id).count()
    )

    # -- Rascunhos de regra: aceitação e correção humana -------------------
    # O catálogo é **global por jurisdição**, não por organização (I4 — fonte
    # legal única). Logo estes números são recortados pelas jurisdições em que
    # a organização tem projeto, e podem incluir trabalho de validação feito
    # por outra organização sobre o mesmo município. É o desenho do catálogo,
    # não um vazamento de tenant: regra não é dado de cliente.
    jurisdictions = applicable_jurisdictions({
        p.city_ibge
        for p in db.query(Project)
        .filter(Project.organization_id == organization_id)
        .all()
        if p.city_ibge
    })

    rules = (
        db.query(RegulatoryRule)
        .filter(RegulatoryRule.jurisdiction.in_(jurisdictions))
        .all()
        if jurisdictions
        else []
    )
    rule_ids = {r.id for r in rules}

    events = (
        db.query(RuleValidationEvent)
        .filter(RuleValidationEvent.rule_id.in_(rule_ids))
        .all()
        if rule_ids
        else []
    )

    # Um rascunho aceito é o que saiu de `rascunho_extraido_por_ia` para
    # `em_validacao`; um recusado é o que foi revogado direto.
    from_draft = [
        e for e in events if e.from_state == RuleState.RASCUNHO_EXTRAIDO_POR_IA
    ]
    accepted = sum(1 for e in from_draft if e.to_state == RuleState.EM_VALIDACAO)
    rejected = sum(1 for e in from_draft if e.to_state == RuleState.REVOGADA)

    still_draft = sum(
        1 for r in rules if r.state == RuleState.RASCUNHO_EXTRAIDO_POR_IA
    )
    drafts_total = len(from_draft) + still_draft

    return {
        "interactions": len(interactions),
        "grounded_percent": _percent(grounded, len(interactions)),
        "served_from_cache_percent": _percent(cached, len(interactions)),
        "failed": failed if interactions else None,
        "input_tokens": input_tokens if with_tokens else None,
        "output_tokens": output_tokens if with_tokens else None,
        "tokens_per_analysis": (
            round((input_tokens + output_tokens) / analyses, 1)
            if with_tokens and analyses
            else None
        ),
        "tokens_per_project": (
            round((input_tokens + output_tokens) / projects, 1)
            if with_tokens and projects
            else None
        ),
        "drafts_extracted": drafts_total if drafts_total else None,
        "drafts_accepted": accepted if drafts_total else None,
        "drafts_rejected": rejected if drafts_total else None,
        "draft_acceptance_percent": _percent(accepted, drafts_total),
    }
