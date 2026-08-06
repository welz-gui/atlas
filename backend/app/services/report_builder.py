"""Montagem do laudo a partir do modelo (§7.5, §12).

Existe para que o endpoint e o worker produzam **o mesmo** documento. Enquanto
a conversão de `AnalysisRun` para os dicionários do gerador vivia dentro do
endpoint, qualquer segundo caminho de emissão — uma fila, um agendamento —
começaria com uma cópia dessa lógica, e duas cópias divergem.

Nada aqui decide se o laudo pode ser entregue: essa resposta já está gravada em
`run.is_publishable`, calculada no momento da análise.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Tuple

from app.models.domain import AnalysisRun, Project
from app.services.pdf_report_generator import RegulatoryReportGenerator


def project_payload(project: Project, run: AnalysisRun) -> Dict[str, Any]:
    """Parâmetros como estavam na versão avaliada — não como estão hoje.

    O laudo retrata a versão que a análise examinou. Ler a versão vigente aqui
    faria o documento descrever um projeto que nunca foi analisado.
    """
    version = run.project_version or project.current_version
    return {
        "id": project.id,
        "name": project.name,
        "city_name": project.city_name,
        "state": project.state,
        "zone": version.zone if version else "—",
        "lot_area": version.lot_area if version else None,
        "built_area": version.built_area if version else None,
        "floors": version.floors if version else None,
        "front_setback": version.front_setback if version else None,
        "rear_setback": version.rear_setback if version else None,
        "occupancy_rate": version.occupancy_rate if version else None,
        "permeability_rate": version.permeability_rate if version else None,
        "is_official_baseline": bool(version and version.is_official_baseline),
        "version_number": version.version_number if version else None,
        "version_state": version.state if version else None,
    }


def validation_payload(run: AnalysisRun) -> List[Dict[str, Any]]:
    return [
        {
            "rule_title": record.rule_title,
            "expected_value": record.expected_value,
            "actual_value": record.actual_value,
            "status": record.status,
            "details": record.details,
            "source_citation": record.source_citation,
            "source_is_verified": record.source_is_verified,
            "evidence_required": record.evidence_required,
        }
        for record in run.validations
    ]


def run_payload(run: AnalysisRun) -> Dict[str, Any]:
    return {
        "id": run.id,
        "content_hash": run.content_hash,
        "catalog_version": run.catalog_version,
        "engine_version": run.engine_version,
        "is_publishable": run.is_publishable,
        "created_at": run.created_at,
    }


def report_filename(project: Project, run: AnalysisRun) -> str:
    """Nome do arquivo — com o prefixo de uso interno quando for o caso (§7.5)."""
    safe_name = "".join(
        c if c.isalnum() or c in "-_" else "_" for c in project.name
    )[:60] or "empreendimento"
    prefix = "" if run.is_publishable else "USO_INTERNO_"
    return f"{prefix}Pre_Analise_{safe_name}.pdf"


def build_report(project: Project, run: AnalysisRun) -> Tuple[bytes, str, str]:
    """Devolve `(pdf, nome do arquivo, sha256 do pdf)`."""
    pdf_bytes = RegulatoryReportGenerator.generate_pdf(
        project_payload(project, run), validation_payload(run), run_payload(run)
    )
    return (
        pdf_bytes,
        report_filename(project, run),
        hashlib.sha256(pdf_bytes).hexdigest(),
    )
