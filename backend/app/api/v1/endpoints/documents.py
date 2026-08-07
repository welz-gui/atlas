"""Gestão documental (§8.3): versionamento, documento vigente, QR Code.

Nenhum caminho de disco aparece neste arquivo. Onde os bytes moram é assunto de
`app.services.storage`; quando eles podem ser descartados, de
`app.services.retention`; se passaram por antivírus, de
`app.services.antivirus`. O endpoint cuida de autorização, do ciclo de vida do
documento e de contar a verdade sobre o que aconteceu com o arquivo.
"""

import io
import os
import re
import urllib.parse
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import (
    get_current_user,
    get_project_or_404,
    get_scoped_or_404,
    require_permission,
    tenant_query,
)
from app.core.config import settings
from app.core.database import get_db
from app.models.domain import Document, DocumentState, User
from app.schemas.domain import DocumentResponse, ExtractionResponse, PurgeReportResponse
from app.services.antivirus import ScanStatus, get_scanner
from app.services.pdf_parser import PDFPlanParser
from app.services.retention import mark_obsolete, purge_expired_documents, retention_deadline
from app.services.storage import ObjectNotFound, build_key, get_storage

router = APIRouter()

#: Extensões aceitas. O nome enviado pelo cliente nunca é usado no
#: armazenamento; a extensão serve para triagem e para nomear a chave interna.
ALLOWED_EXTENSIONS = {
    ".pdf", ".dxf", ".ifc", ".txt", ".csv",
    ".png", ".jpg", ".jpeg", ".webp",
    ".xlsx", ".xls", ".docx", ".doc",
}

CHUNK_SIZE = 1024 * 1024


def secure_filename(filename: str) -> str:
    """Limpa o nome do arquivo, prevenindo path traversal de Windows e injeção de headers."""
    if not filename:
        return ""
    # Decodifica caracteres URL-encoded (ex: %22 vira ", %2e%2e%2f vira ../)
    filename = urllib.parse.unquote(filename)
    # Trata separadores de diretório do Windows, mesmo rodando em Linux
    filename = filename.replace("\\", "/")
    filename = os.path.basename(filename)
    # Remove aspas, caracteres de controle e de redirecionamento que possam afetar os headers
    filename = re.sub(r'[\r\n"\'<>|\0]', '_', filename)
    return filename


@router.post(
    "/projects/{project_id}/documents/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    project_id: str,
    title: str = Form(...),
    category: str = Form("projeto_arquitetonico"),
    version: str = Form("v1.0"),
    supersedes_id: Optional[str] = Form(None),
    file: UploadFile = File(...),
    user: User = Depends(require_permission("document:write")),
    db: Session = Depends(get_db),
):
    project = get_project_or_404(db, project_id, user)

    superseded: Optional[Document] = None
    if supersedes_id:
        superseded = (
            tenant_query(db, Document, user)
            .filter(Document.id == supersedes_id, Document.project_id == project_id)
            .first()
        )
        if not superseded:
            raise HTTPException(
                status_code=404, detail="Documento a ser substituído não encontrado."
            )

    # O nome enviado pelo cliente é tratado como dado hostil: dele só se
    # aproveita a extensão, e ainda assim contra uma allowlist. A chave no
    # armazenamento é opaca e gerada pelo servidor, de modo que sequências como
    # "../" não têm efeito algum.
    original_filename = secure_filename(file.filename or "")
    extension = os.path.splitext(original_filename)[1].lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"Extensão '{extension or 'desconhecida'}' não permitida. "
                f"Aceitas: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
            ),
        )

    storage = get_storage()
    key = build_key(extension)
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024

    # `defer_commit` mantém os bytes em arquivo temporário até a varredura
    # terminar: arquivo infectado nunca chega a existir no armazenamento.
    writer = storage.writer(key, defer_commit=True)
    try:
        with writer:
            while chunk := await file.read(CHUNK_SIZE):
                if writer.write(chunk) > max_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"Arquivo excede o limite de {settings.MAX_UPLOAD_MB} MB.",
                    )

        if writer.size_bytes == 0:
            writer.abort()
            raise HTTPException(status_code=400, detail="Arquivo vazio.")

        scan = get_scanner().scan_file(writer.temp_path)

        if scan.is_infected:
            writer.abort()
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Arquivo recusado pelo antivírus: {scan.signature or 'ameaça detectada'}."
                ),
            )

        if not scan.is_clean and settings.ANTIVIRUS_REQUIRED:
            # Falhar fechado: com varredura obrigatória, 'não sabemos' vale
            # como recusa. O detalhe do motor vai na resposta para que o
            # operador consiga distinguir clamd fora do ar de arquivo suspeito.
            writer.abort()
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "Upload recusado: a varredura antivírus é obrigatória nesta "
                    f"instalação e não pôde ser concluída ({scan.detail or scan.status})."
                ),
            )

        stored = writer.commit()
    except HTTPException:
        writer.abort()
        raise
    except Exception:
        writer.abort()
        raise

    document = Document(
        organization_id=user.organization_id,
        project_id=project_id,
        project_version_id=project.current_version.id if project.current_version else None,
        title=title,
        category=category,
        version=version,
        file_path=stored.key,
        storage_backend=stored.backend,
        original_filename=original_filename or None,
        content_type=file.content_type,
        size_bytes=stored.size_bytes,
        hash_sha256=stored.sha256,
        antivirus_status=scan.status,
        antivirus_engine=scan.engine,
        antivirus_engine_version=scan.engine_version,
        antivirus_signature=scan.signature,
        antivirus_scanned_at=scan.scanned_at,
        status=DocumentState.VIGENTE,
        supersedes_id=superseded.id if superseded else None,
        uploaded_by_id=user.id,
    )
    db.add(document)

    # A versão anterior sai de circulação no mesmo ato (§8.3 — bloqueio de
    # versão obsoleta). Duas versões vigentes do mesmo documento seriam uma
    # ambiguidade perigosa em obra. É aqui também que a retenção começa a
    # contar para o arquivo substituído.
    if superseded:
        mark_obsolete(superseded)

    db.commit()
    db.refresh(document)
    return document


@router.get("/projects/{project_id}/documents", response_model=List[DocumentResponse])
def list_project_documents(
    project_id: str,
    include_obsolete: bool = True,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_project_or_404(db, project_id, user)
    query = tenant_query(db, Document, user).filter(Document.project_id == project_id)
    if not include_obsolete:
        query = query.filter(Document.status != DocumentState.OBSOLETO)
    return query.order_by(Document.created_at.desc()).all()


@router.get("/documents/{document_id}/download")
def download_document(
    document_id: str,
    user: User = Depends(require_permission("document:read")),
    db: Session = Depends(get_db),
):
    """Devolve o binário do documento.

    Duas respostas negativas são distintas de propósito: `410 Gone` quando o
    arquivo foi expurgado pela política de retenção — situação prevista, com
    data e motivo registrados — e `404` quando ele sumiu do armazenamento sem
    explicação, que é incidente e não rotina.
    """
    document = get_scoped_or_404(db, Document, document_id, user, "Documento")

    if document.is_purged:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail=(
                f"Arquivo expurgado em {document.purged_at:%d/%m/%Y} pela política "
                f"de retenção. O registro do documento permanece disponível. "
                f"{document.purge_reason or ''}".strip()
            ),
        )

    storage = get_storage()
    try:
        chunks = storage.stream(document.file_path)
        first = next(chunks, b"")
    except ObjectNotFound:
        raise HTTPException(
            status_code=404,
            detail="Arquivo não encontrado no armazenamento.",
        )

    def body():
        yield first
        yield from chunks

    filename = document.original_filename or f"{document.title}{os.path.splitext(document.file_path)[1]}"
    filename = secure_filename(filename)
    return StreamingResponse(
        body(),
        media_type=document.content_type or "application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Atlas-Document-Status": document.status,
            "X-Atlas-Antivirus-Status": document.antivirus_status,
        },
    )


@router.post("/documents/{document_id}/obsolete", response_model=DocumentResponse)
def mark_document_obsolete(
    document_id: str,
    user: User = Depends(require_permission("document:write")),
    db: Session = Depends(get_db),
):
    document = get_scoped_or_404(db, Document, document_id, user, "Documento")
    mark_obsolete(document)
    db.commit()
    db.refresh(document)
    return document


@router.post("/storage/purge-expired", response_model=PurgeReportResponse)
def purge_expired(
    dry_run: bool = True,
    user: User = Depends(require_permission("org:manage")),
    db: Session = Depends(get_db),
):
    """Executa a política de retenção sobre a própria organização (§6.6).

    Só descarta o binário; o registro do documento permanece. O padrão é
    simulação: para apagar de fato é preciso pedir `dry_run=false`.
    """
    report = purge_expired_documents(
        db, organization_id=user.organization_id, dry_run=dry_run
    )
    return PurgeReportResponse(
        dry_run=report.dry_run,
        retention_enabled=report.retention_enabled,
        retention_days=settings.OBSOLETE_RETENTION_DAYS,
        examined=report.examined,
        purged=report.purged,
        already_missing=report.already_missing,
        failed=report.failed,
        document_ids=report.document_ids,
        errors=report.errors,
    )


@router.get("/documents/{document_id}/qrcode")
def document_qrcode(
    document_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """QR Code de verificação do documento (§8.3).

    Codifica identificador, versão, situação e hash — de modo que quem estiver
    com a prancha impressa em obra possa conferir se ainda é a versão vigente.
    """
    import qrcode
    import qrcode.image.svg

    document = get_scoped_or_404(db, Document, document_id, user, "Documento")

    payload = (
        f"{settings.PUBLIC_BASE_URL}/verificar/documento/{document.id}"
        f"?v={document.version}&s={document.status}&h={(document.hash_sha256 or '')[:16]}"
    )
    image = qrcode.make(payload, image_factory=qrcode.image.svg.SvgImage)
    buffer = io.BytesIO()
    image.save(buffer)

    return Response(
        content=buffer.getvalue(),
        media_type="image/svg+xml",
        headers={
            "X-Atlas-Document-Status": document.status,
            "X-Atlas-Document-Version": document.version,
            "Cache-Control": "no-store",
        },
    )


@router.post(
    "/projects/{project_id}/documents/{document_id}/extract",
    response_model=ExtractionResponse,
)
def extract_document_parameters(
    project_id: str,
    document_id: str,
    user: User = Depends(require_permission("document:read")),
    db: Session = Depends(get_db),
):
    """Extração assistida — nunca devolve um valor que não estava no documento."""
    get_project_or_404(db, project_id, user)
    document = (
        tenant_query(db, Document, user)
        .filter(Document.id == document_id, Document.project_id == project_id)
        .first()
    )
    if not document:
        raise HTTPException(status_code=404, detail="Documento não encontrado.")

    if document.status == DocumentState.OBSOLETO:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Este documento está marcado como obsoleto e não pode alimentar uma "
                "análise. Use a versão vigente."
            ),
        )

    if document.is_purged:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Arquivo expurgado pela política de retenção; não há o que extrair.",
        )

    try:
        content_bytes = get_storage().read(document.file_path)
    except ObjectNotFound:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Arquivo do documento não está mais disponível no armazenamento.",
        )

    result = PDFPlanParser.parse_file(
        content_bytes, document.original_filename or document.title
    )

    parameters = {
        key: result.get(key)
        for key in (
            "lot_area", "built_area", "front_setback",
            "rear_setback", "permeability_rate", "floors",
        )
    }

    return ExtractionResponse(
        document_id=document.id,
        document_title=document.title,
        status=result["status"],
        fields_found=result["fields_found"],
        fields_expected=result["fields_expected"],
        extracted_parameters=parameters,
        evidence=result.get("evidence") or [],
        warnings=result.get("warnings") or [],
    )
