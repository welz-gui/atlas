"""Motor de regras determinístico (§3.4).

O motor não conhece nenhuma regra: ele carrega o catálogo regulatório e
executa apenas as regras em estado executável. Toda execução gera um
`AnalysisRun` novo — nada é sobrescrito nem apagado (§3.5).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.domain import AnalysisRun, Project, ValidationRecord
from app.regulatory.catalog import CheckOutcome, Rule, catalog

ENGINE_VERSION = "1.1.0"

#: Parâmetros do empreendimento expostos às regras.
PARAM_FIELDS = (
    "zone",
    "building_type",
    "lot_area",
    "built_area",
    "floors",
    "front_setback",
    "side_setback",
    "rear_setback",
    "permeability_rate",
    "parking_spaces",
)


class RegulatoryEngine:
    @staticmethod
    def project_params(project: Project) -> Dict[str, Any]:
        params = {name: getattr(project, name) for name in PARAM_FIELDS}
        # Derivado — ver Project.occupancy_rate.
        params["occupancy_rate"] = project.occupancy_rate
        return params

    @staticmethod
    def _content_hash(
        project: Project, params: Dict[str, Any], results: List[Dict[str, Any]]
    ) -> str:
        """SHA-256 sobre o conteúdo canônico da análise.

        Cobre os parâmetros avaliados, as regras aplicadas e os resultados —
        de modo que o selo do laudo comprove *o que foi analisado*, e não
        apenas o instante da emissão.
        """
        payload = {
            "project_id": project.id,
            "jurisdiction": project.city_ibge,
            "engine_version": ENGINE_VERSION,
            "catalog_version": catalog.version_for(project.city_ibge),
            "params": {k: params[k] for k in sorted(params)},
            "results": sorted(
                (
                    {
                        "rule_id": r["rule_id"],
                        "rule_state": r["rule_state"],
                        "status": r["status"],
                        "expected": r["expected_value"],
                        "actual": r["actual_value"],
                    }
                    for r in results
                ),
                key=lambda item: item["rule_id"],
            ),
        }
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @classmethod
    def _build_result(cls, rule: Rule, params: Dict[str, Any]) -> Dict[str, Any]:
        evaluation = rule.evaluate(params)
        return {
            "rule_id": rule.rule_id,
            "rule_title": rule.title,
            "field": (rule.check or {}).get("field", "analise_documental"),
            "status": evaluation["outcome"],
            "expected_value": rule.expected_label(),
            "actual_value": evaluation["actual_label"],
            "details": evaluation["details"],
            "rule_state": rule.state,
            "severity": rule.severity,
            "method": "analise_manual" if rule.requires_manual_review else "regra_deterministica",
            "source_document": rule.source.document,
            "source_article": rule.source.article,
            "source_citation": rule.source.citation(),
            "source_is_verified": rule.source.is_verified,
            "evidence_required": ", ".join(rule.evidence_required) or None,
            "validated_by": rule.validated_by,
            "is_publishable": rule.is_publishable,
        }

    @classmethod
    def evaluate_project(
        cls,
        db: Session,
        project: Project,
        trigger: str = "manual",
    ) -> AnalysisRun:
        """Executa o catálogo sobre o projeto e persiste uma nova análise.

        Devolve o `AnalysisRun` criado. Análises anteriores permanecem
        intactas.
        """
        params = cls.project_params(project)
        jurisdiction = project.city_ibge

        rules = [
            rule
            for rule in catalog.executable_for(jurisdiction)
            if rule.applies_to_project(params, jurisdiction)
        ]
        results = [cls._build_result(rule, params) for rule in rules]

        run = AnalysisRun(
            project_id=project.id,
            organization_id=project.organization_id,
            jurisdiction=jurisdiction,
            catalog_version=catalog.version_for(jurisdiction),
            engine_version=ENGINE_VERSION,
            trigger=trigger,
            total_checks=len(results),
            conforme_count=sum(1 for r in results if r["status"] == CheckOutcome.CONFORME),
            nao_conforme_count=sum(1 for r in results if r["status"] == CheckOutcome.NAO_CONFORME),
            atencao_count=sum(1 for r in results if r["status"] == CheckOutcome.ATENCAO),
            nao_verificavel_count=sum(
                1 for r in results if r["status"] == CheckOutcome.NAO_VERIFICAVEL
            ),
            # §7.5 — o laudo só é publicável se toda regra aplicada estiver
            # validada. Uma análise sem regra alguma também não é publicável.
            is_publishable=bool(results) and all(r["is_publishable"] for r in results),
            content_hash=cls._content_hash(project, params, results),
        )
        db.add(run)
        db.flush()

        for result in results:
            db.add(
                ValidationRecord(
                    analysis_run_id=run.id,
                    project_id=project.id,
                    **result,
                )
            )

        db.commit()
        db.refresh(run)
        return run

    @staticmethod
    def latest_run(db: Session, project_id: str) -> Optional[AnalysisRun]:
        return (
            db.query(AnalysisRun)
            .filter(AnalysisRun.project_id == project_id)
            .order_by(AnalysisRun.created_at.desc(), AnalysisRun.id.desc())
            .first()
        )
