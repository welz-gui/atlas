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
from app.regulatory.catalog import RuleState


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

        total_reqs = len(reqs)
        predicted_reqs = sum(1 for r in reqs if r.was_predicted)
        unpredicted_reqs = total_reqs - predicted_reqs

        recall = (predicted_reqs / total_reqs * 100.0) if total_reqs > 0 else 100.0

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
        print(f"  * Exigências Reais Registradas:   {total_reqs}")
        print(f"  * Exigências Previstas pelo Atlas: {predicted_reqs}")
        print(f"  * Recall de Bloqueios/Exigências:  {recall:.1f}%")
        print(f"  * Falsos Negativos Críticos:      {unpredicted_reqs}")
        print("-" * 70)
        print("DISTRIBUIÇÃO DOS VEREDICTOS DE ANÁLISE")
        print(f"  * Verificações Conformes:          {conformes}")
        print(f"  * Verificações Não Conformes:      {bloqueios}")
        print(f"  * Verificações Não Verificáveis:   {nao_verificaveis}")
        print("=" * 70)

        print("\nDETALHAMENTO POR PROJETO:")
        for p in projects:
            p_reqs = db.query(ProtocolRequirement).filter(
                ProtocolRequirement.process_id.in_(
                    db.query(ProtocolProcess.id).filter_by(project_id=p.id)
                )
            ).all()
            print(f"  - [{p.name}] | Tipologia: {p.use_type} | Exigências: {len(p_reqs)}")

        print("\n[OK] Relatório concluído. Estágio 0 pronto para validação operacional.")

    finally:
        db.close()


if __name__ == "__main__":
    generate_stage0_report()
