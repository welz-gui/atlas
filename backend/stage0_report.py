"""Relatório de Acurácia e Desempenho do Estágio 0 (Concierge) — Atlas.

Consolida as métricas da §11 do Plano de Implementação:
  - Recall de exigências do órgão
  - Falsos Negativos Críticos
  - Regras vigentes vs. em validação no catálogo
  - Taxa de não verificáveis

Uso:
    python stage0_report.py
"""

from app.core.database import SessionLocal
from app.models.domain import (
    Organization,
    Project,
    AnalysisRun,
    ValidationRecord,
    ProtocolProcess,
    ProtocolRequirement,
    RegulatoryRule,
)
from collections import defaultdict
from app.regulatory.catalog import RuleState
from app.services.metrics import approval_metrics

SEM_BASE = "n/d (sem base amostral)"


def _valor(numero, sufixo=""):
    """Ausência de base é dita como ausência — nunca vira 0 nem 100%."""
    return SEM_BASE if numero is None else f"{numero}{sufixo}"


def requirement_lines(approval):
    """Linhas do bloco de recall, a partir de `approval_metrics`."""
    return [
        f"  * Exigências Reais Registradas:   {_valor(approval['requirements_total'])}",
        f"  * Vinculadas a uma Regra:         {_valor(approval['requirements_linked_to_rules'])}",
        f"  * Recall de Bloqueios/Exigências:  {_valor(approval['blocking_recall_percent'], '%')}",
        f"  * Falsos Negativos Críticos:      {_valor(approval['critical_false_negatives'])}",
    ]


def generate_stage0_report():
    db = SessionLocal()
    try:
        org = db.query(Organization).filter(Organization.name.like("%Concierge%")).first()
        if not org:
            print("⚠️ Nenhuma organização de Concierge encontrada. Execute `python stage0_concierge_seed.py` primeiro.")
            return

        projects = db.query(Project).filter_by(organization_id=org.id).all()
        regras = db.query(RegulatoryRule).filter_by(jurisdiction="BR-RS-4311403").all()

        regras_vigentes = sum(1 for r in regras if r.state == RuleState.VIGENTE)
        regras_em_validacao = sum(1 for r in regras if r.state == RuleState.EM_VALIDACAO)

        total_projects = len(projects)
        total_analyses = db.query(AnalysisRun).filter(AnalysisRun.project_id.in_([p.id for p in projects])).count()

        # Requisitos de protocolo
        processes = db.query(ProtocolProcess).filter(ProtocolProcess.project_id.in_([p.id for p in projects])).all()
        proc_ids = [pr.id for pr in processes]
        reqs = db.query(ProtocolRequirement).filter(ProtocolRequirement.process_id.in_(proc_ids)).all() if proc_ids else []

        # O critério é o das métricas do §11 (`/metrics`): só entra a exigência
        # vinculada a uma regra, e sem base amostral o número é ausente.
        approval = approval_metrics(db, org.id)

        # Não verificáveis nos ValidationRecords
        val_records = db.query(ValidationRecord).filter(
            ValidationRecord.analysis_run_id.in_(
                db.query(AnalysisRun.id).filter(AnalysisRun.project_id.in_([p.id for p in projects]))
            )
        ).all()

        nao_verificaveis = sum(1 for v in val_records if v.status == "nao_verificavel")
        bloqueios = sum(1 for v in val_records if v.status == "nao_conforme")
        conformes = sum(1 for v in val_records if v.status == "conforme")

        print("=" * 70)
        print("         ATLAS — RELATÓRIO DE DESEMPENHO DO ESTÁGIO 0 (CONCIERGE)")
        print("=" * 70)
        print(f"Organização:             {org.name}")
        print(f"Projetos de Pré-análise: {total_projects}")
        print(f"Análises Executadas:    {total_analyses}")
        print("-" * 70)
        print("MÉTRICAS DO CATÁLOGO REGULATÓRIO (Lajeado/RS BR-RS-4311403)")
        print(f"  * Regras Vigentes (Conferidas):    {regras_vigentes}")
        print(f"  * Regras em Validação:            {regras_em_validacao}")
        print(f"  * Total de Regras no Catálogo:    {len(regras)}")
        print("-" * 70)
        print("MÉTRICAS DE ACURÁCIA PREDITIVA E RECALL (§11 DO PLANO)")
        for line in requirement_lines(approval):
            print(line)
        print("-" * 70)
        print("DISTRIBUIÇÃO DOS VEREDICTOS DE ANÁLISE")
        print(f"  * Verificações Conformes:          {conformes}")
        print(f"  * Verificações Não Conformes:      {bloqueios}")
        print(f"  * Verificações Não Verificáveis:   {nao_verificaveis}")
        print("=" * 70)

        proc_to_proj = {pr.id: pr.project_id for pr in processes}
        proj_req_count = defaultdict(int)
        for r in reqs:
            proj_id = proc_to_proj.get(r.process_id)
            if proj_id:
                proj_req_count[proj_id] += 1

        print("\nDETALHAMENTO POR PROJETO:")
        for p in projects:
            print(f"  - [{p.name}] | Tipologia: {p.use_type} | Exigências: {proj_req_count[p.id]}")

        print("\n[OK] Relatório concluído. Estágio 0 pronto para validação operacional.")

    finally:
        db.close()


if __name__ == "__main__":
    generate_stage0_report()
