"""Executores dos trabalhos assíncronos (§6.7).

Cada função aqui recebe a sessão e o registro do trabalho, e devolve um
dicionário que vira `job_records.result`. O que ela **não** faz é decidir
regra de negócio própria: a extração continua sendo `PDFPlanParser`, a análise
continua sendo `RegulatoryEngine`. Tirar o trabalho do request não muda o que
ele faz nem afrouxa nenhuma garantia — em particular, um laudo continua só
sendo publicável se todas as regras aplicadas estiverem validadas (§7.5).
"""

from __future__ import annotations

from typing import Any, Dict

from sqlalchemy.orm import Session

from app.models.domain import Document, DocumentState, JobRecord, JobType, Project, User
from app.services.pdf_parser import PDFPlanParser
from app.services.regulatory_engine import RegulatoryEngine
from app.services.retention import purge_expired_documents
from app.services.storage import ObjectNotFound, get_storage
from app.workers.queue import register


def _scoped_project(db: Session, record: JobRecord, project_id: str) -> Project:
    """Carrega o projeto conferindo a organização do trabalho.

    O worker roda fora do contexto da requisição, sem `get_current_user`. O
    isolamento entre organizações (§3.1) tem de ser refeito aqui, à mão: o
    trabalho carrega a organização de quem o pediu, e nada além dela é visível.
    """
    project = (
        db.query(Project)
        .filter(
            Project.id == project_id,
            Project.organization_id == record.organization_id,
        )
        .first()
    )
    if project is None:
        raise LookupError(
            f"Empreendimento '{project_id}' não encontrado na organização do trabalho."
        )
    return project


@register(JobType.EXTRACAO_DOCUMENTO)
def extract_document(db: Session, record: JobRecord) -> Dict[str, Any]:
    """Extrai parâmetros de um documento — sem inventar valor algum."""
    document_id = record.payload.get("document_id")
    if not document_id:
        raise ValueError("payload.document_id é obrigatório.")

    document = (
        db.query(Document)
        .filter(
            Document.id == document_id,
            Document.organization_id == record.organization_id,
        )
        .first()
    )
    if document is None:
        raise LookupError(f"Documento '{document_id}' não encontrado.")

    if document.status == DocumentState.OBSOLETO:
        raise ValueError(
            "Documento obsoleto não alimenta análise; use a versão vigente (§8.3)."
        )
    if document.is_purged:
        raise ValueError("Arquivo expurgado pela política de retenção (§6.6).")

    try:
        content = get_storage().read(document.file_path)
    except ObjectNotFound as exc:
        raise LookupError("Arquivo não está mais disponível no armazenamento.") from exc

    result = PDFPlanParser.parse_file(
        content, document.original_filename or document.title
    )
    return {
        "document_id": document.id,
        "status": result["status"],
        "fields_found": result["fields_found"],
        "fields_expected": result["fields_expected"],
        "extracted_parameters": {
            key: result.get(key)
            for key in (
                "lot_area", "built_area", "front_setback",
                "rear_setback", "permeability_rate", "floors",
            )
        },
        "evidence": result.get("evidence") or [],
        "warnings": result.get("warnings") or [],
    }


@register(JobType.ANALISE_REGULATORIA)
def run_analysis(db: Session, record: JobRecord) -> Dict[str, Any]:
    """Executa o catálogo sobre uma versão do projeto (§3.4)."""
    project_id = record.payload.get("project_id") or record.project_id
    if not project_id:
        raise ValueError("payload.project_id é obrigatório.")

    project = _scoped_project(db, record, project_id)

    version = None
    version_id = record.payload.get("project_version_id")
    if version_id:
        version = next((v for v in project.versions if v.id == version_id), None)
        if version is None:
            raise LookupError(f"Versão '{version_id}' não pertence a este projeto.")

    requester = (
        db.query(User).filter(User.id == record.requested_by_id).first()
        if record.requested_by_id
        else None
    )

    run = RegulatoryEngine.evaluate_project(
        db,
        project,
        trigger=record.payload.get("trigger", "assincrono"),
        user=requester,
        version=version,
    )
    return {
        "analysis_run_id": run.id,
        "project_version_number": run.project_version_number,
        "total_checks": run.total_checks,
        "nao_conforme_count": run.nao_conforme_count,
        "nao_verificavel_count": run.nao_verificavel_count,
        "is_publishable": run.is_publishable,
        "content_hash": run.content_hash,
    }


@register(JobType.GERACAO_LAUDO)
def generate_report(db: Session, record: JobRecord) -> Dict[str, Any]:
    """Gera o PDF do laudo e o guarda no storage.

    O laudo entra no armazenamento como qualquer outro binário, com chave
    opaca — e o resultado do trabalho aponta para ela. Nenhuma ressalva do
    §12 é dispensada por o PDF ter sido produzido fora do request: quem monta
    o documento continua sendo o mesmo gerador.
    """
    from app.models.domain import AnalysisRun
    from app.services.report_builder import build_report
    from app.services.storage import build_key

    project_id = record.payload.get("project_id") or record.project_id
    if not project_id:
        raise ValueError("payload.project_id é obrigatório.")

    project = _scoped_project(db, record, project_id)

    run_id = record.payload.get("analysis_run_id")
    if run_id:
        run = (
            db.query(AnalysisRun)
            .filter(AnalysisRun.id == run_id, AnalysisRun.project_id == project.id)
            .first()
        )
        if run is None:
            raise LookupError(f"Análise '{run_id}' não pertence a este empreendimento.")
    else:
        run = RegulatoryEngine.latest_run(db, project.id)

    if run is None:
        raise ValueError(
            "Nenhuma análise registrada para este empreendimento; não há o que emitir."
        )

    pdf_bytes, filename, pdf_sha256 = build_report(project, run)

    key = build_key(".pdf")
    storage = get_storage()
    with storage.writer(key) as writer:
        writer.write(pdf_bytes)
    stored = writer.result

    return {
        "analysis_run_id": run.id,
        "storage_key": stored.key,
        "storage_backend": stored.backend,
        "filename": filename,
        "size_bytes": stored.size_bytes,
        "sha256": pdf_sha256,
        # Repetido aqui de propósito: quem só olhar o resultado do trabalho
        # precisa ver que o laudo é de uso interno, sem ter de ir à análise.
        "is_publishable": run.is_publishable,
    }


@register(JobType.EXPURGO_RETENCAO)
def purge_retention(db: Session, record: JobRecord) -> Dict[str, Any]:
    """Aplica a política de retenção da organização do trabalho (§6.6)."""
    report = purge_expired_documents(
        db,
        organization_id=record.organization_id,
        dry_run=bool(record.payload.get("dry_run", False)),
    )
    return {
        "dry_run": report.dry_run,
        "examined": report.examined,
        "purged": report.purged,
        "already_missing": report.already_missing,
        "failed": report.failed,
        "document_ids": report.document_ids,
        "errors": report.errors,
    }


@register(JobType.DESCOBERTA_REGULATORIA)
def discover_regulatory_documents(db: Session, record: JobRecord) -> Dict[str, Any]:
    """Consulta índices oficiais e cria somente candidatos para revisão humana."""
    from app.regulatory.discovery import discover_applicable_regulations

    jurisdiction = record.payload.get("jurisdiction")
    if not jurisdiction:
        raise ValueError("payload.jurisdiction é obrigatório.")
    return discover_applicable_regulations(db, jurisdiction)
