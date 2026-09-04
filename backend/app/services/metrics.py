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
from sqlalchemy import func, and_

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


def _calculate_notification_metrics(db: Session, organization_id: str, process_ids: list[str]) -> int:
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


def _calculate_duration_metrics(processes: list[ProtocolProcess]) -> tuple[list[float], int]:
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


def _calculate_recall_metrics(requirements: list[ProtocolRequirement]) -> tuple[list[ProtocolRequirement], int, int]:
    linked = [r for r in requirements if r.linked_rule_key]
    predicted = sum(1 for r in linked if r.was_predicted)
    false_negatives = sum(1 for r in linked if r.was_predicted is False)
    return linked, predicted, false_negatives


def _get_latest_runs_by_project(db: Session, organization_id: str, project_ids: list[str]) -> dict[str, AnalysisRun]:
    latest_runs_by_project = {}
    if project_ids:
        subquery = (
            db.query(
                AnalysisRun.project_id,
                func.max(AnalysisRun.created_at).label("max_created_at"),
            )
            .filter(
                AnalysisRun.organization_id == organization_id,
                AnalysisRun.project_id.in_(project_ids),
            )
            .group_by(AnalysisRun.project_id)
            .subquery()
        )

        latest_runs_list = (
            db.query(AnalysisRun)
            .join(
                subquery,
                and_(
                    AnalysisRun.project_id == subquery.c.project_id,
                    AnalysisRun.created_at == subquery.c.max_created_at,
                ),
            )
            .filter(AnalysisRun.organization_id == organization_id)
            .all()
        )
        latest_runs_by_project = {run.project_id: run for run in latest_runs_list}
    return latest_runs_by_project


def _calculate_precision_metrics(processes: list[ProtocolProcess], requirements: list[ProtocolRequirement], latest_runs_by_project: dict[str, AnalysisRun]) -> tuple[int, int]:
    protocolled_project_ids = {p.project_id for p in processes}
    required_pairs = {
        (process.project_id, r.linked_rule_key)
        for process in processes
        for r in requirements
        if r.process_id == process.id and r.linked_rule_key
    }

    flagged_pairs: set[tuple[str, str]] = set()
    for project_id in protocolled_project_ids:
        latest = latest_runs_by_project.get(project_id)
        if not latest:
            continue
        for record in latest.validations:
            if record.status in FLAGGED:
                flagged_pairs.add((project_id, record.rule_id))

    confirmed = len(flagged_pairs & required_pairs)
    return confirmed, len(flagged_pairs)


def _calculate_unverifiable_metrics(project_ids: list[str], latest_runs_by_project: dict[str, AnalysisRun]) -> tuple[int, int]:
    total_checks = 0
    unverifiable = 0
    for project_id in project_ids:
        latest = latest_runs_by_project.get(project_id)
        if not latest:
            continue
        total_checks += latest.total_checks
        unverifiable += latest.nao_verificavel_count
    return total_checks, unverifiable


def _calculate_catalog_metrics(db: Session, projects: list[Project]) -> tuple[int, int, int]:
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
    return len(jurisdictions) if jurisdictions else 0, len(rules), publishable


def approval_metrics(db: Session, organization_id: str) -> dict[str, Any]:
    projects = (
        db.query(Project).filter(Project.organization_id == organization_id).all()
    )
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

    notification_events = _calculate_notification_metrics(db, organization_id, process_ids)
    durations, approved = _calculate_duration_metrics(processes)
    linked, predicted, false_negatives = _calculate_recall_metrics(requirements)

    latest_runs_by_project = _get_latest_runs_by_project(db, organization_id, project_ids)
    confirmed, flagged_pairs_count = _calculate_precision_metrics(processes, requirements, latest_runs_by_project)
    total_checks, unverifiable = _calculate_unverifiable_metrics(project_ids, latest_runs_by_project)
    jurisdictions_len, rules_len, publishable = _calculate_catalog_metrics(db, projects)

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
        "precision_percent": _percent(confirmed, flagged_pairs_count),
        "unverifiable_percent": _percent(unverifiable, total_checks),
        "catalog_rules": rules_len if jurisdictions_len else None,
        "catalog_publishable_rules": publishable if jurisdictions_len else None,
        "catalog_coverage_percent": _percent(publishable, rules_len),
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
        i
        for i in interactions
        if i.input_tokens is not None or i.output_tokens is not None
    ]
    input_tokens = sum(i.input_tokens or 0 for i in with_tokens)
    output_tokens = sum(i.output_tokens or 0 for i in with_tokens)

    analyses = (
        db.query(AnalysisRun)
        .filter(AnalysisRun.organization_id == organization_id)
        .count()
    )
    projects_list = (
        db.query(Project).filter(Project.organization_id == organization_id).all()
    )
    projects = len(projects_list)

    # -- Rascunhos de regra: aceitação e correção humana -------------------
    # O catálogo é **global por jurisdição**, não por organização (I4 — fonte
    # legal única). Logo estes números são recortados pelas jurisdições em que
    # a organização tem projeto, e podem incluir trabalho de validação feito
    # por outra organização sobre o mesmo município. É o desenho do catálogo,
    # não um vazamento de tenant: regra não é dado de cliente.
    jurisdictions = applicable_jurisdictions(
        {
            p.city_ibge
            for p in projects_list
            if p.city_ibge
        }
    )

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

    still_draft = sum(1 for r in rules if r.state == RuleState.RASCUNHO_EXTRAIDO_POR_IA)
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
